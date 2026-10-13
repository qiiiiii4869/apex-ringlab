import assert from "node:assert/strict";
import {fitCircle, validRing} from "../web/geometry.mjs";

const points = [{x:11000,y:8000},{x:8000,y:11000},{x:5000,y:8000}];
assert.deepEqual(fitCircle(points),{x:8000,y:8000,r:3000});
assert.deepEqual(fitCircle([points[2],points[0],points[1]]),{x:8000,y:8000,r:3000});
assert.throws(()=>fitCircle([{x:1000,y:1000},{x:2000,y:2000},{x:3000,y:3000}]),/分散/);
assert.throws(()=>fitCircle([{x:NaN,y:1000},{x:2000,y:2000},{x:3000,y:1000}]),/有效/);
assert.equal(validRing({x:"",y:8000,r:3000}),false);
assert.equal(validRing({x:8000,y:8000,r:Infinity}),false);
console.log("6 browser-independent geometry checks passed.");
