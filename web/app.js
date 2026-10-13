"use strict";
import {validRing, fitCircle} from "/geometry.mjs";
import {SESSION_KEY, savedPrefix, mergeRings, restoreSession} from "/session.mjs";
const $ = (id) => document.getElementById(id);
const SIZE = 16384;
const NS = "http://www.w3.org/2000/svg";
const state = {meta:null,count:1,rings:[{},{},{}],result:null,revision:0,busy:false,selected:0,view:{x:0,y:0,w:SIZE},drawing:null,points:[],drag:null,pending:null,cropPoints:[],uploadToken:0,recognitionToken:0,isExample:false,storageAvailable:true};
const colors = {known:"#f1d987",model:"#ff8d74",candidate:"#69d9d1",baseline:"#c8a6ee"};
const predictionColors = ["#ffcf66","#6dded1","#c5adff","#ff9b96","#97c4ff"];
function percent(value) {return `${(value*100).toFixed(1)}%`;}

async function api(path, body) {
  const controller = new AbortController(), timer = setTimeout(()=>controller.abort(),75000);
  try {
    const response = await fetch(path, {...(body === undefined ? {} : {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)}),signal:controller.signal});
    const text = await response.text();
    let data; try {data=JSON.parse(text);} catch {data={};}
    if (!response.ok) throw new Error(data.error || (response.status===413?"截图请求过大，请压缩后重试。已有圈位已保留。":response.status===429||response.status===503?"服务繁忙，请稍后重试。已有圈位已保留。":"服务处理失败，请稍后重试。"));
    if (!Object.keys(data).length) throw new Error("服务响应无效，请稍后重试。");
    return data;
  } catch(error) {if(error.name==="AbortError")throw new Error("请求超时，请稍后重试。已有圈位已保留。");throw error;}
  finally {clearTimeout(timer);}
}
function message(text, error=false) {$("form-status").textContent=text;$("form-status").classList.toggle("error",error);}
function svgNode(tag, attrs={}, text) {const node=document.createElementNS(NS,tag);for(const [key,value] of Object.entries(attrs))node.setAttribute(key,String(value));if(text!==undefined)node.textContent=text;return node;}
function coordinates(ring) {return `${Math.round(ring.x).toLocaleString("en-US")} / ${Math.round(ring.y).toLocaleString("en-US")}`;}
function observed() {return state.rings.slice(0,state.count).map((r,i)=>({stage:i+1,x:Number(r.x),y:Number(r.y),r:Number(r.r)}));}
function currentRings() {return state.isExample?[]:savedPrefix(state.rings);}
function persistSession() {try {if(state.isExample||state.rings.every(ring=>Object.keys(ring).length===0))sessionStorage.removeItem(SESSION_KEY);else sessionStorage.setItem(SESSION_KEY,JSON.stringify({version:1,rings:state.rings,count:state.count}));}catch{state.storageAvailable=false;}}
function updateMatchProgress() {const count=currentRings().length;$("match-progress").textContent=state.isExample?"当前为历史示例，请开始新对局后记录游戏圈位":count?`本局已记录第 1${count>1?`～${count}`:""} 圈${count===3?" · 已达到当前支持的 3 圈":""}`:"本局尚未记录圈位";$("continue-upload").disabled=count===0||count===3;$("continue-upload").textContent=count===3?"已记录前三圈":"继续上传本局截图";$("match-persistence").textContent=state.storageAvailable?"圈位保存在当前标签页，刷新后可继续。":"浏览器保存不可用，当前页面内仍可继续上传。";}
function updateButton() {$("predict").disabled=!state.meta||state.busy||!$("map-confirmed").checked||!state.rings.slice(0,state.count).every(validRing);updateMatchProgress();}
function invalidate() {state.revision++;state.result=null;$("results").hidden=true;$("result-placeholder").hidden=false;persistSession();draw();updateButton();}
function renderEditors() {
  const holder=$("ring-editors");holder.replaceChildren();
  for(let i=0;i<state.count;i++) {
    const wrapper=document.createElement("div");wrapper.className="ring-editor";wrapper.dataset.stage=String(i+1);
    const head=document.createElement("div");head.className="ring-editor-header";
    const title=document.createElement("label");title.textContent=`第 ${i+1} 圈`;head.append(title);
    const mark=document.createElement("button");mark.type="button";mark.textContent="边界取 3 点 ↗";mark.setAttribute("aria-label",`在地图上标记第 ${i+1} 圈的三个边界点`);mark.addEventListener("click",()=>startDrawing(i));head.append(mark);wrapper.append(head);
    const row=document.createElement("div");row.className="field-row";
    for(const [key,label,placeholder] of [["x","圆心 X","8192"],["y","圆心 Y","8192"],["r","半径 R",i===0?"4825":i===1?"2367":"1457"]]) {
      const field=document.createElement("label");field.textContent=label;
      const input=document.createElement("input");input.type="number";input.min=key==="r"?"1":"0";input.max=String(SIZE);input.step="any";input.placeholder=placeholder;input.value=state.rings[i][key]??"";input.setAttribute("aria-label",`第 ${i+1} 圈${label}`);
      input.addEventListener("input",()=>{state.rings[i][key]=input.value;stopDrawing();invalidate();message("圈位已变更，请重新确认并预测。");$("map-confirmed").checked=false;updateButton();});field.append(input);row.append(field);
    }
    wrapper.append(row);holder.append(wrapper);
  }
  document.querySelectorAll("[data-count]").forEach(button=>{const active=Number(button.dataset.count)===state.count;button.classList.toggle("active",active);button.setAttribute("aria-pressed",String(active));});
  updateButton();
}
function setRings(rings, example=false) {stopDrawing();state.isExample=example;state.rings=[{},{},{}];rings.forEach((r,i)=>{state.rings[i]={x:Math.round(r.x),y:Math.round(r.y),r:Math.round(r.r)};});state.count=rings.length||1;$("map-confirmed").checked=example;invalidate();renderEditors();resetView();message(example?"已载入历史示例圈位；可直接预测。这不是你当前对局。":"请确认圈位、圈次与地图，再开始预测。");}
function newMatch() {state.uploadToken++;state.recognitionToken++;state.pending=null;if($("screenshot-dialog").open)$("screenshot-dialog").close();$("screenshot-layer").removeAttribute("href");$("screenshot-toggle-label").hidden=true;$("show-screenshot").checked=false;$("show-all-known").checked=false;$("screenshot-status").textContent="已开始新对局，请上传首圈截图。";setRings([]);message("已清空上一局圈位与预测。上传首圈后可继续补充后续圈。");}
function circle(layer, ring, color, label, options={}) {
  if(!validRing(ring))return;
  const group=svgNode("g");group.append(svgNode("circle",{cx:ring.x,cy:ring.y,r:ring.r,fill:color,"fill-opacity":options.fill??.055,stroke:color,"stroke-width":options.width??2,"vector-effect":"non-scaling-stroke",...(options.dashed?{"stroke-dasharray":"7 6"}:{})}));
  const marker=svgNode("path",{d:`M ${Number(ring.x)-85} ${ring.y} h170 M ${ring.x} ${Number(ring.y)-85} v170`,stroke:color,"stroke-width":1.5,"vector-effect":"non-scaling-stroke"});group.append(marker);
  group.append(svgNode("title",{},`${label}：X ${Math.round(ring.x)}，Y ${Math.round(ring.y)}，R ${Math.round(ring.r)}`));layer.append(group);
}
function draw() {
  for(const id of ["known-layer","candidate-layer","draft-layer"])$(id).replaceChildren();
  state.rings.slice(0,state.count).forEach((ring,i)=>{if(i===state.count-1||$("show-all-known").checked)circle($("known-layer"),ring,colors.known,`本局已知第 ${i+1} 圈`,{dashed:true,fill:0,width:i===state.count-1?2:1});});
  if(state.result) {
    state.result.predictions.slice(0,5).forEach((candidate,i)=>{
      const ring=candidate.final_ring,color=predictionColors[i];
      const selected=i===state.selected;
      if(selected || $("show-all-predictions").checked)circle($("candidate-layer"),ring,color,`预测 ${i+1}，估计命中概率 ${percent(candidate.probability.value)}`,{fill:selected ? .12 : 0,width:selected?3:1.5});
      const font=state.view.w*.017;
      const badge=svgNode("g",{"pointer-events":"none","data-prediction":i+1});
      const labelY=selected?ring.y-ring.r-font*.5:ring.y;
      const halfWidth=font*(selected?3.7:.9);
      badge.append(svgNode("rect",{x:ring.x-halfWidth,y:labelY-font*.85,width:halfWidth*2,height:font*1.65,rx:font*.3,fill:"#101916","fill-opacity":.94,stroke:color,"stroke-width":1,"vector-effect":"non-scaling-stroke"}));
      badge.append(svgNode("text",{x:ring.x,y:labelY+font*.35,fill:color,"font-size":font,"font-weight":600,"text-anchor":"middle"},selected?`${i+1} · ${percent(candidate.probability.value)}`:String(i+1)));
      badge.append(svgNode("title",{},`预测 ${i+1}，估计命中概率 ${percent(candidate.probability.value)}`));
      $("candidate-layer").append(badge);
    });
  }
  for(const point of state.points)$("draft-layer").append(svgNode("circle",{cx:point.x,cy:point.y,r:55,fill:colors.known,stroke:"#111c17","stroke-width":1,"vector-effect":"non-scaling-stroke"}));
  $("map-empty").hidden=state.rings.slice(0,state.count).some(validRing)||Boolean(state.result)||Boolean($("screenshot-layer").getAttribute("href"));
  updateVisibility();
}
function updateVisibility() {for(const [checkbox,layer] of [["show-known","known-layer"],["show-candidates","candidate-layer"],["show-screenshot","screenshot-layer"]])$(layer).style.display=$(checkbox).checked?"":"none";}
function setView(x,y,w) {w=Math.max(1024,Math.min(SIZE,w));state.view={x:Math.max(0,Math.min(SIZE-w,x)),y:Math.max(0,Math.min(SIZE-w,y)),w};const v=state.view;$("map-svg").setAttribute("viewBox",`${v.x} ${v.y} ${v.w} ${v.w}`);draw();}
function resetView() {setView(0,0,SIZE);}
function zoom(factor,point) {const v=state.view;point=point||{x:v.x+v.w/2,y:v.y+v.w/2};const w=Math.max(1024,Math.min(SIZE,v.w*factor));const actual=w/v.w;setView(point.x-(point.x-v.x)*actual,point.y-(point.y-v.y)*actual,w);}
function focusRing(ring) {stopDrawing();const w=Math.max(2400,Math.min(SIZE,ring.r*3.4));setView(ring.x-w/2,ring.y-w/2,w);}
function pointOnSvg(svg,event) {const matrix=svg.getScreenCTM();if(!matrix)return null;const point=new DOMPoint(event.clientX,event.clientY).matrixTransform(matrix.inverse());return{x:point.x,y:point.y};}
function startDrawing(index) {state.drawing=index;state.points=[];$("drawing-hint").hidden=false;$("drawing-hint").textContent=`第 ${index+1} 圈：在安全区边界选取 3 个分散的点（Esc 取消）`;$("map-stage").style.cursor="crosshair";document.querySelectorAll(".ring-editor").forEach((el,i)=>el.classList.toggle("active-drawing",i===index));$("map-stage").scrollIntoView({behavior:"smooth",block:"nearest"});draw();}
function stopDrawing() {state.drawing=null;state.points=[];$("drawing-hint").hidden=true;$("map-stage").style.cursor="";document.querySelectorAll(".ring-editor").forEach(el=>el.classList.remove("active-drawing"));}
function addBoundaryPoint(point) {
  if(point.x<0||point.x>SIZE||point.y<0||point.y>SIZE)return;
  state.points.push(point);draw();
  if(state.points.length<3){$("drawing-hint").textContent=`第 ${state.drawing+1} 圈：已选 ${state.points.length}/3 点，继续选择边界`;return;}
  try {const index=state.drawing,ring=fitCircle(state.points);const draft=state.rings.map(r=>({...r}));draft[index]={x:Math.round(ring.x),y:Math.round(ring.y),r:Math.round(ring.r)};if(draft.slice(0,state.count).every(validRing))mergeRings([],savedPrefix(draft.slice(0,state.count)));state.rings=draft;stopDrawing();$("map-confirmed").checked=false;invalidate();renderEditors();message(`第 ${index+1} 圈已由边界点拟合，请核对圈次并确认。`);}catch(error){state.points=[];draw();$("drawing-hint").textContent=error.message;}
}
function renderResults(result) {
  $("results").hidden=false;$("result-placeholder").hidden=true;
  $("prediction-count").textContent=`${result.predictions.length} 个结果 · 已合并相近圈位`;
  $("matching-status").textContent={exact:"精确历史匹配",near:"相近圈型",distant:"匹配较远",empty:"暂无匹配"}[result.retrieval.status]||"待核对";
  $("matching-message").textContent=result.retrieval.message;$("probability-note").textContent=result.probability_note;
  const list=$("candidate-list");list.replaceChildren();
  result.predictions.slice(0,5).forEach((candidate,index)=>{
    const button=document.createElement("button");button.className="candidate-item"+(index===state.selected?" active":"");button.setAttribute("aria-pressed",String(index===state.selected));
    const rank=document.createElement("span");rank.className="rank";rank.textContent=String(index+1).padStart(2,"0");rank.style.color=predictionColors[index];
    const name=document.createElement("span");name.className="candidate-name";name.textContent=candidate.label;const position=document.createElement("small");position.textContent=coordinates(candidate.final_ring);name.append(position);
    const probability=document.createElement("span");probability.className="candidate-probability";probability.textContent=percent(candidate.probability.value);
    const caption=document.createElement("small");caption.textContent="估计命中概率";probability.append(caption);
    const interval=candidate.probability.interval_95;probability.title=`历史参考 ${candidate.probability.sample_count} 条；95% 抽样区间 ${percent(interval[0])}～${percent(interval[1])}。未计入截图误差及版本差异。`;
    button.append(rank,name,probability);
    button.addEventListener("click",()=>{state.selected=index;$("show-candidates").checked=true;renderResults(state.result);draw();focusRing(candidate.final_ring);});list.append(button);
  });
  draw();
}
async function predict() {
  if($("predict").disabled)return;stopDrawing();const revision=state.revision;state.busy=true;updateButton();$("predict").firstChild.textContent="正在计算… ";message("正在对照模型与历史圈型…");
  try {const result=await api("/api/predict",{known_rings:observed(),...state.meta.scope});if(state.revision!==revision)return;state.result=result;state.selected=0;$("show-screenshot").checked=false;focusRing(result.known_rings[result.known_rings.length-1]);renderResults(result);message(`已显示 ${result.predictions.length} 个预测结果。默认展开所选圈，其余编号可在右侧点击定位。`);}
  catch(error){if(state.revision===revision)message(error.message,true);}
  finally {state.busy=false;$("predict").firstChild.textContent="在地图上预测 ";updateButton();}
}

function readFile(file) {return new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=()=>reject(new Error("图片读取失败"));reader.readAsDataURL(file);});}
function showCrop() {
  $("crop-area").hidden=false;$("recognized-area").hidden=true;state.cropPoints=[];$("apply-crop").disabled=true;
  const image=$("original-screenshot");image.onload=()=>{$("crop-svg").setAttribute("viewBox",`0 0 ${image.naturalWidth} ${image.naturalHeight}`);$("crop-svg").replaceChildren();};image.src=state.pending.original;
}
async function recognize(bounds) {
  const token=state.uploadToken,recognitionToken=++state.recognitionToken;state.pending.recognition=null;$("recognized-area").hidden=true;$("dialog-status").textContent=bounds?"正在按选定地图区域换算圈位…":"正在尝试定位世界尽头地图并寻找圆弧…";$("apply-crop").disabled=true;
  try {
    const result=await api("/api/recognize",{image:state.pending.original,...(bounds?{bounds}: {})});if(token!==state.uploadToken||recognitionToken!==state.recognitionToken)return;state.pending.recognition=result;$("dialog-status").textContent=result.message;
    if(result.status==="needs_map_bounds"){showCrop();return;}
    $("crop-area").hidden=true;$("recognized-area").hidden=false;$("aligned-preview").src=result.aligned_image;renderRecognition(result.candidates);
  }catch(error){if(token===state.uploadToken&&recognitionToken===state.recognitionToken){$("dialog-status").textContent=error.message;showCrop();}}
}
function renderRecognition(candidates) {
  const list=$("recognition-list");list.replaceChildren();
  const overlay=$("recognition-overlay");overlay.replaceChildren();
  if(!candidates.length){const note=document.createElement("p");note.className="small-note";note.textContent="未找到可靠圆弧。可叠加截图，在主地图上取 3 个边界点。";list.append(note);}
  candidates.forEach((ring,i)=>{const color=predictionColors[i%5];circle(overlay,ring,color,`识别圈 ${i+1}`,{fill:0,width:2});overlay.append(svgNode("text",{x:ring.x,y:ring.y-240,fill:color,"font-size":450,"font-weight":700,"text-anchor":"middle",stroke:"#101916","stroke-width":70,"paint-order":"stroke"},String(i+1)));const row=document.createElement("label");row.className="recognition-row";const text=document.createElement("span");text.textContent=`识别圈 ${i+1}`;text.style.color=color;const details=document.createElement("small");details.textContent=`${coordinates(ring)} · R ${Math.round(ring.r)}`;text.append(details);const select=document.createElement("select");select.setAttribute("aria-label",`识别圈 ${i+1} 的圈次`);for(const [value,label] of [[0,"不采用"],[1,"第 1 圈"],[2,"第 2 圈"],[3,"第 3 圈"]]){const option=document.createElement("option");option.value=String(value);const saved=value>0&&value<=state.pending.baseRings.length;option.textContent=label+(saved?"（已保存）":"");option.disabled=saved;select.append(option);}if(candidates.length===1&&state.pending.baseRings.length>0)select.value=String(state.pending.baseRings.length+1);select.dataset.candidate=String(i);row.append(text,select);list.append(row);});
  $("apply-detected").disabled=candidates.length===0;
}
function applyScreenshot() {const result=state.pending.recognition;$("screenshot-layer").setAttribute("href",result.aligned_image);$("show-screenshot").checked=true;$("screenshot-toggle-label").hidden=false;$("screenshot-status").textContent="截图已叠加。请核对地图对齐与安全区圈次；识别结果需确认。";}
function applyDetected() {
  if(!state.pending?.recognition||state.pending.recognition.status!=="aligned")return;
  if(state.pending.baseRevision!==state.revision){$("dialog-status").textContent="本局信息已变化，请关闭窗口并重新上传。";return;}
  const selected=[];for(const select of $("recognition-list").querySelectorAll("select")){const stage=Number(select.value);if(stage)selected.push({...state.pending.recognition.candidates[Number(select.dataset.candidate)],stage});}
  selected.sort((a,b)=>a.stage-b.stage);
  if(!selected.length){$("dialog-status").textContent="请确认至少一个圆弧的圈次，或选择手动取点。";return;}
  try {const merged=mergeRings(state.pending.baseRings,selected),previous=state.pending.baseRings.length;applyScreenshot();setRings(merged);$("show-all-known").checked=merged.length>1;draw();if(previous)message(`已保留本局前 ${previous} 圈，合并后共 ${merged.length} 圈。确认后将一起用于预测。`);$("screenshot-dialog").close();state.pending=null;}catch(error){$("dialog-status").textContent=error.message;}
}
function manualScreenshot() {if(!state.pending?.recognition||state.pending.recognition.status!=="aligned")return;if(state.pending.baseRevision!==state.revision){$("dialog-status").textContent="本局信息已变化，请重新上传。";return;}const base=state.pending.baseRings;applyScreenshot();setRings(base);state.count=base.length+1;invalidate();renderEditors();$("show-all-known").checked=base.length>0;$("screenshot-dialog").close();state.pending=null;startDrawing(base.length);message(`此前 ${base.length} 圈已保留，请在新截图上标记第 ${base.length+1} 圈。`);}
function cropClick(event) {
  if(!state.pending)return;const point=pointOnSvg($("crop-svg"),event);const image=$("original-screenshot");
  if(!point||point.x<0||point.x>image.naturalWidth||point.y<0||point.y>image.naturalHeight)return;
  if(state.cropPoints.length===2)state.cropPoints=[];state.cropPoints.push(point);const svg=$("crop-svg");svg.replaceChildren();
  state.cropPoints.forEach(p=>svg.append(svgNode("circle",{cx:p.x,cy:p.y,r:8,fill:colors.known})));
  if(state.cropPoints.length===2){const [a,b]=state.cropPoints;svg.append(svgNode("rect",{x:Math.min(a.x,b.x),y:Math.min(a.y,b.y),width:Math.abs(a.x-b.x),height:Math.abs(a.y-b.y),fill:colors.known,"fill-opacity":.08,stroke:colors.known,"stroke-width":3,"vector-effect":"non-scaling-stroke"}));}
  $("apply-crop").disabled=state.cropPoints.length!==2;
}

document.querySelectorAll("[data-count]").forEach(button=>button.addEventListener("click",()=>{stopDrawing();state.count=Number(button.dataset.count);$("map-confirmed").checked=false;invalidate();renderEditors();message("请补齐并确认连续的已知圈。");}));
$("map-confirmed").addEventListener("change",updateButton);$("predict").addEventListener("click",predict);
$("load-example").addEventListener("click",()=>{if(!state.meta){message("本地服务尚未连接，请稍后重试。",true);return;}$("screenshot-layer").removeAttribute("href");$("screenshot-toggle-label").hidden=true;$("screenshot-status").textContent="当前是历史示例坐标，不是你的游戏截图。";setRings(state.meta.example.known_rings,true);});
for(const id of ["show-known","show-candidates","show-screenshot"])$(id).addEventListener("change",updateVisibility);
$("show-all-known").addEventListener("change",draw);
$("show-all-predictions").addEventListener("change",draw);
$("zoom-in").addEventListener("click",()=>zoom(.75));$("zoom-out").addEventListener("click",()=>zoom(1/.75));$("reset-view").addEventListener("click",resetView);
$("map-svg").addEventListener("wheel",event=>{event.preventDefault();const point=pointOnSvg($("map-svg"),event);if(point)zoom(event.deltaY>0?1.15:1/1.15,point);},{passive:false});
$("map-svg").addEventListener("pointerdown",event=>{if(event.button!==0)return;state.drag={x:event.clientX,y:event.clientY,view:{...state.view},moved:false};$("map-svg").setPointerCapture(event.pointerId);});
$("map-svg").addEventListener("pointermove",event=>{const point=pointOnSvg($("map-svg"),event);if(point)$("pointer-coordinates").textContent=`X ${Math.round(point.x)}　Y ${Math.round(point.y)}`;if(!state.drag)return;const dx=event.clientX-state.drag.x,dy=event.clientY-state.drag.y;if(Math.hypot(dx,dy)>5)state.drag.moved=true;if(state.drawing===null){const rect=$("map-svg").getBoundingClientRect(),scale=state.drag.view.w/Math.min(rect.width,rect.height);setView(state.drag.view.x-dx*scale,state.drag.view.y-dy*scale,state.drag.view.w);}});
$("map-svg").addEventListener("pointerup",event=>{if(state.drag&&!state.drag.moved&&state.drawing!==null){const point=pointOnSvg($("map-svg"),event);if(point)addBoundaryPoint(point);}state.drag=null;});$("map-svg").addEventListener("pointercancel",()=>{state.drag=null;});
document.addEventListener("keydown",event=>{if(event.key==="Escape"){stopDrawing();draw();}});
async function uploadScreenshot(event) {const file=event.target.files[0];if(!file)return;const baseRings=currentRings();if(baseRings.length===3){$("screenshot-status").textContent="本局已记录前三圈，当前模型最多支持 3 圈。另一把游戏请先开始新对局。";event.target.value="";return;}if(!["image/jpeg","image/png"].includes(file.type)||file.size>8*1024*1024){$("screenshot-status").textContent="请选择不超过 8 MB 的 JPG 或 PNG 文件。已有圈位已保留。";event.target.value="";return;}const token=++state.uploadToken,baseRevision=state.revision;try{const original=await readFile(file);if(token!==state.uploadToken)return;state.pending={original,baseRings,baseRevision};$("upload-context").textContent=baseRings.length?`继续本局：已保存第 1${baseRings.length>1?`～${baseRings.length}`:""} 圈，本次补充第 ${baseRings.length+1} 圈。旧圈无需出现在新截图中。`:"本局首次上传：请选择首圈；如果截图含多个圈，可以一起采用。";$("apply-detected").textContent=baseRings.length?"合并到本局圈位":"采用所选圈位";$("crop-area").hidden=true;$("recognized-area").hidden=true;$("screenshot-dialog").showModal();await recognize();}catch(error){if(token===state.uploadToken)$("screenshot-status").textContent=error.message;}finally{event.target.value="";}}
$("screenshot-input").addEventListener("change",uploadScreenshot);$("continue-screenshot-input").addEventListener("change",uploadScreenshot);
$("continue-upload").addEventListener("click",()=>{$("continue-screenshot-input").click();});$("new-match").addEventListener("click",newMatch);
$("close-screenshot").addEventListener("click",()=>{$("screenshot-dialog").close();state.uploadToken++;state.pending=null;});$("screenshot-dialog").addEventListener("cancel",()=>{state.uploadToken++;state.pending=null;});
$("crop-svg").addEventListener("click",cropClick);$("reset-crop").addEventListener("click",showCrop);$("redo-crop").addEventListener("click",showCrop);
$("apply-crop").addEventListener("click",()=>{if(state.cropPoints.length===2){const [a,b]=state.cropPoints;recognize({x0:Math.min(a.x,b.x),y0:Math.min(a.y,b.y),x1:Math.max(a.x,b.x),y1:Math.max(a.y,b.y)});}});
$("use-full-image").addEventListener("click",()=>{const image=$("original-screenshot");if(image.naturalWidth&&image.naturalHeight)recognize({x0:0,y0:0,x1:image.naturalWidth,y1:image.naturalHeight});});
$("apply-detected").addEventListener("click",applyDetected);$("manual-from-screenshot").addEventListener("click",manualScreenshot);
try {const saved=restoreSession(sessionStorage.getItem(SESSION_KEY));if(saved){state.rings=saved.rings;state.count=saved.count;$("show-all-known").checked=currentRings().length>1;if(state.rings.some(ring=>Object.keys(ring).length>0))message("已恢复本局圈位，可继续上传后续截图。请核对后重新预测。");}}catch{state.storageAvailable=false;}
renderEditors();draw();
api("/api/meta").then(meta=>{state.meta=meta;$("image-processing").textContent=meta.processing.notice;$("service-mode").textContent=meta.processing.mode==="local"?"本地研究版":"研究试用版";$("sample-count").textContent=`${meta.count.toLocaleString("en-US")} 条样本`;$("reference-count").textContent=`正式库 ${meta.count} 条（PUBLIC ${meta.public_count} / ALGS ${meta.algs_count}）；本页参考库为 ${meta.reference_count} 条固定排位训练样本。`;updateButton();}).catch(error=>{message(`服务不可用：${error.message}`,true);$("sample-count").textContent="服务连接失败";});
