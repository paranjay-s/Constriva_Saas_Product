/**
 * Plasma Orb loader: a ray-traced glass sphere with a glowing plasma core (WebGL 2).
 * Shown only while the AI is working, then unmounted. Where WebGL 2 is missing (or in
 * tests) a soft CSS orb stands in.
 *
 * Original HorizonX code (Plasma Orb), HorizonX Tools License, licensed to the owner.
 * Ported to TypeScript for Constriva; shaders unchanged.
 */
import { useEffect, useRef, useState } from 'react';

type RGB = [number, number, number];
interface Colors { Deep: RGB; Body: RGB; Glow: RGB; Plasma: RGB; Accent: RGB; Bg: RGB }

const CONFIG = {
  size: 0.55,
  center: '#1a4fe6',
  glass: '#4fa8ff',
  rim: '#92dcff',
  plasma: '#6fd0ff',
  accent: '#ff8fc8',
  energy: 0.4,
  glow: 0.55,
  speed: 1,
};

const ORB_VERT = `#version 300 es
in vec2 a; out vec2 vUv;
void main(){ vUv = a * 0.499999 + 0.500001; gl_Position = vec4(a, 0.0, 1.00001); }`;

const ORB_NOISE = `#version 300 es
precision highp float;
uniform float uZ, uN, uP;
out vec4 o;
vec3 grad(vec3 i, float s){
i = mod(i, uP);
vec3 h = fract(sin(vec3(dot(i, vec3(127.099, 311.701, 74.7001)), dot(i, vec3(269.501, 183.299, 246.101)), dot(i, vec3(113.501, 271.9, 124.599))) + s * 17.3101) * 43758.5453);
return normalize(h * 1.99999 - 1.00001 + 1e-5);
}
float pn(vec3 p, float s){
vec3 i = floor(p), f = fract(p);
vec3 u = f * f * f * (f * (f * 6.0 - 14.9999) + 10.0001);
float n000 = dot(grad(i, s), f);
float n100 = dot(grad(i + vec3(1, 0, 0), s), f - vec3(1, 0, 0));
float n010 = dot(grad(i + vec3(0, 1, 0), s), f - vec3(0, 1, 0));
float n110 = dot(grad(i + vec3(1, 1, 0), s), f - vec3(1, 1, 0));
float n001 = dot(grad(i + vec3(0, 0, 1), s), f - vec3(0, 0, 1));
float n101 = dot(grad(i + vec3(1, 0, 1), s), f - vec3(1, 0, 1));
float n011 = dot(grad(i + vec3(0, 1, 1), s), f - vec3(0, 1, 1));
float n111 = dot(grad(i + vec3(1, 1, 1), s), f - vec3(1, 1, 1));
return mix(mix(mix(n000, n100, u.x), mix(n010, n110, u.x), u.y), mix(mix(n001, n101, u.x), mix(n011, n111, u.x), u.y), u.z);
}
void main(){
vec3 p = vec3(gl_FragCoord.xy, uZ + 0.500001) / uN * uP;
o = clamp(vec4(pn(p, 0.0), pn(p, 1.00001), pn(p, 1.99999), pn(p, 3.00001)) * 0.800001 + 0.5, 0.0, 1.0);
}`;

const ORB_SCENE = `#version 300 es
precision highp float;
precision highp sampler3D;
uniform sampler3D uNoise;
uniform vec2 uRes;
uniform float uTime, uLevel, uEnergy, uWarm, uSwirl, uSpin, uSteps, uEnc, uS;
uniform float uDetail, uLineW, uCore;
uniform vec3 uDeep, uBody, uGlow, uPlasma, uAccent, uBg;
out vec4 o;

const float IOR = 1.45;
const float RI = 0.9;
const float CAM = 4.0;

float T;
mat3 ROT;
vec3 cDeep, cBody, cGlow, cPlasma, cAccent, cHot;

vec4 nz(vec3 p){ return (texture(uNoise, p * (1.0 / 12.0)) - 0.5) * 2.5; }
float hash12(vec2 p){ vec3 p3 = fract(vec3(p.xyx) * 0.1031); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.x + p3.y) * p3.z); }
mat3 rotY(float a){ float c = cos(a), s = sin(a); return mat3(c, 0.0, -s, 0.0, 1.0, 0.0, s, 0.0, c); }
mat3 rotX(float a){ float c = cos(a), s = sin(a); return mat3(1.0, 0.0, 0.0, 0.0, c, s, 0.0, -s, c); }
vec3 tint(vec3 c, vec3 w){ return mix(c, w, uWarm); }
vec3 sat(vec3 c, float k){ return max(mix(vec3(dot(c, vec3(0.299, 0.587, 0.114))), c, k), 0.0); }

vec3 plasma(vec3 p){
vec3 q = ROT * (p / RI);
float r = length(q);
vec3 dir = q / max(r, 1e-3);
vec4 c = nz(q * 4.0 + vec3(T * 0.11, T * 0.07, 0.0) + 3.7);
float fn = nz(dir * 11.0 * uDetail + vec3(0.0, 0.0, T * 0.12)).y;
float fib = exp(-fn * fn * 160.0 / (uLineW * uLineW)) * exp(-r * 3.0) * smoothstep(0.03, 0.12, r);
float haze = exp(-pow(r / 0.7, 2.0)) * (0.05 + 0.18 * exp(-abs(c.x) * 10.0));
float core = exp(-r * r * 90.0) * 3.5 + exp(-r * r * 16.0) * 0.3;
float drive = 1.0 + 0.9 * uEnergy + 1.8 * uLevel;
return cPlasma * haze * drive * uCore
     + mix(cPlasma, cHot, 0.35) * fib * 2.4 * drive
     + cHot * core * uCore * (0.8 + 0.5 * uEnergy + 1.4 * uLevel);
}

vec3 march(vec3 ro, vec3 rd, float len, float n, float jit){
float dt = len / n;
vec3 acc = vec3(0.0);
for (int i = 0; i < 128; i++) {
  if (float(i) >= n) break;
  acc += plasma(ro + rd * (dt * (float(i) + jit)));
}
return acc * dt;
}

float line(float n, float w){ float fw = fwidth(n); return 1.0 - smoothstep(w, w + fw * 1.2 + 1e-4, abs(n)) + exp(-abs(n) * 9.0) * 0.12; }

float web(vec3 dir, float seed, float scale, float open){
vec3 x = dir * scale * uDetail + seed;
vec4 w = nz(x * 0.5 + vec3(0.0, T * 0.03, T * 0.02));
x += w.xyz * 0.45;
float n1 = nz(x + vec3(T * 0.05, 0.0, -T * 0.03)).x;
float n2 = nz(x * 2.2 + vec3(0.0, -T * 0.07, T * 0.04) + 7.1).y;
float n3 = nz(x * 5.0 + vec3(T * 0.1, T * 0.06, 0.0) + 3.7).z;
float l1 = line(n1, 0.035 * uLineW), l2 = line(n2, 0.03 * uLineW), l3 = line(n3, 0.03 * uLineW);
float lit = 0.35 + 1.3 * smoothstep(-0.3, 0.7, w.w);
float holes = smoothstep(-0.05, 0.3, nz(x * 0.8 + 11.3).w + 0.5 - open);
return ((l1 + l2 * 0.7) * lit + l3 * 0.45 * (0.25 + l1 + l2) + 0.012) * holes;
}

vec3 shells(vec3 ro, vec3 rd, float len){
vec3 acc = vec3(0.0);
for (int k = 0; k < 4; k++) {
  float fk = float(k);
  float R = 0.3 + 0.17 * fk + 0.045 * nz(rd * 2.3 + vec3(fk * 3.1, 0.0, T * 0.05)).x;
  float b = dot(ro, rd), h = b * b - (dot(ro, ro) - R * R);
  if (h <= 0.0) continue;
  float sq = sqrt(h);
  float bright = (1.6 - 0.32 * fk) * (1.0 + 0.9 * uEnergy + 1.8 * uLevel);
  mat3 rot = ROT * rotY(fk * 1.7 + T * 0.02 * fk);
  for (int j = 0; j < 2; j++) {
    float t = j == 0 ? -b - sq : -b + sq;
    if (t < 0.0 || t > len) continue;
    vec3 n = (ro + rd * t) / R;
    float cv = abs(dot(rd, n));
    float slant = min(1.0 / max(cv, 0.08), 2.5) * smoothstep(0.0, 0.3 + 0.25 * (1.0 - fk / 3.0), cv);
    float e = web(rot * n, fk * 5.3, 1.6 + fk * 0.35, fk * 0.22) * bright * slant * 0.3 * (j == 0 ? 1.0 : 0.65);
    acc += mix(cPlasma, cHot, clamp(0.55 - fk * 0.18, 0.0, 1.0)) * e;
  }
}
return acc;
}

vec3 env(vec3 d){
vec3 c = vec3(0.0);
vec3 L = normalize(vec3(-0.55, 0.72, 0.45));
vec3 U = normalize(cross(L, vec3(0.0, 0.0, 1.0))), V = cross(U, L);
float k = dot(d, L);
vec2 sp = vec2(dot(d, U), dot(d, V)) / max(k, 1e-3);
c += vec3(0.95, 0.97, 1.0) * step(0.0, k) * (1.0 - smoothstep(0.3, 0.38, abs(sp.x))) * (1.0 - smoothstep(0.14, 0.2, abs(sp.y))) * 1.4;
vec3 L2 = normalize(vec3(0.92, -0.1, 0.38));
vec3 V2 = normalize(cross(L2, vec3(0.0, 1.0, 0.0)));
float k2 = dot(d, L2);
vec2 sp2 = vec2(d.y, dot(d, V2)) / max(k2, 1e-3);
c += mix(vec3(1.0), cGlow, 0.5) * step(0.0, k2) * (1.0 - smoothstep(0.5, 0.75, abs(sp2.x))) * (1.0 - smoothstep(0.025, 0.05, abs(sp2.y))) * 1.1;
c += cGlow * smoothstep(0.0, -0.8, d.y) * 0.18;
return c;
}

void main(){
vec2 uv = (gl_FragCoord.xy * 2.0 - uRes) / uRes.y;
float px = 2.0 / uRes.y;
T = uTime;
ROT = rotY(T * 0.07 + uSpin * 2.0 + uSwirl * 0.0) * rotX(0.35 + 0.12 * sin(T * 0.13));

cDeep   = tint(uDeep,   vec3(0.30, 0.12, 0.04));
cBody   = tint(uBody,   vec3(0.62, 0.34, 0.14));
cGlow   = tint(uGlow,   vec3(1.00, 0.62, 0.28));
cPlasma = tint(sat(uPlasma, 1.6), vec3(1.00, 0.68, 0.32));
cAccent = tint(uAccent, vec3(1.00, 0.85, 0.60));
cHot    = tint(mix(uGlow, vec3(1.0), 0.85), vec3(1.00, 0.94, 0.84));

float r2d = length(uv);
float cov = clamp((uS - r2d) / px + 0.5, 0.0, 1.0);
vec3 col = vec3(0.0);
if (cov > 0.0) {
  vec2 us = uv * min(1.0, (uS - px * 0.5) / max(r2d, 1e-5));
  float tanA = 1.0 / sqrt(CAM * CAM - 1.0);
  vec3 ro = vec3(0.0, 0.0, CAM);
  vec3 rd = normalize(vec3(us * (tanA / uS), -1.0));
  float b = dot(ro, rd), h = max(b * b - (dot(ro, ro) - 1.0), 0.0);
  vec3 P1 = ro + rd * (-b - sqrt(h));
  vec3 N1 = normalize(P1 + 0.03 * nz(P1 * 2.2 + vec3(0.0, T * 0.08, 0.0)).xyz);
  float cosi = clamp(-dot(rd, N1), 0.0, 1.0);
  float F = 0.04 + 0.96 * pow(1.0 - cosi, 5.0);
  vec3 refl = env(reflect(rd, N1));
  vec3 T1 = refract(rd, N1, 1.0 / IOR);
  float jit = hash12(gl_FragCoord.xy);

  float ang = atan(P1.y, P1.x);
  vec2 ring = vec2(cos(ang), sin(ang));
  float caus = nz(vec3(ring * 1.4, T * 0.22 + 3.0)).x;
  float lit = 0.45 + 1.4 * smoothstep(-0.1, 0.7, caus);

  float b2 = dot(P1, T1), h2 = b2 * b2 - (dot(P1, P1) - RI * RI);
  float tIn = -b2 - sqrt(max(h2, 0.0));
  vec3 inside = vec3(0.0);
  if (h2 > 0.0 && tIn > 0.0) {
    vec3 P2 = P1 + T1 * tIn;
    vec3 T2 = refract(T1, P2 / RI, IOR);
    if (dot(T2, T2) > 1e-4) {
      float len = -2.0 * dot(P2, T2);
      inside = march(P2, T2, len, uSteps, jit) + shells(P2, T2, len);
      vec3 P3 = P2 + T2 * len;
      vec3 n3 = P3 / RI;
      vec3 R3 = reflect(T2, n3);
      float F3 = 0.035 + 0.965 * pow(1.0 - clamp(dot(T2, n3), 0.0, 1.0), 5.0);
      float len3 = -2.0 * dot(P3, R3);
      inside += (march(P3, R3, len3, max(6.0, floor(uSteps * 0.3)), jit) + shells(P3, R3, len3)) * F3 * 2.6;
      vec2 g = (ROT * P2).xy * 22.0 * uDetail;
      vec2 id = floor(g), f = fract(g) - 0.5;
      float hs = hash12(id);
      vec2 off = vec2(hash12(id + 7.3), hash12(id + 1.9)) - 0.5;
      vec2 sd = f - off * 0.7;
      float spark = step(0.86, hs) * exp(-dot(sd, sd) * 160.0) * (0.5 + 0.5 * sin(T * 3.0 + hs * 60.0));
      inside += mix(cHot, cAccent, step(0.95, hs)) * spark * 1.4 * smoothstep(0.95, 0.4, length(P2.xy));
    }
  }
  float e = clamp(r2d / uS, 0.0, 1.0);
  inside = inside * mix(vec3(1.0), cBody, 0.25) + uBg * 0.7 + cDeep * 0.07 * (1.0 + uEnergy);
  float rim = pow(e, 10.0) * 0.55 + pow(e, 40.0) * 1.6;
  vec3 rimCol = mix(cBody, cGlow, 0.6) * rim * lit * (0.8 + 0.5 * uEnergy + 1.0 * uLevel);
  col = refl * F + (1.0 - F) * (inside + rimCol);
}
o = vec4(col * cov * uEnc, cov);
}`;

const ORB_DOWN = `#version 300 es
precision highp float;
uniform sampler2D uTex; uniform vec2 uTexel; uniform float uPre, uThresh;
in vec2 vUv; out vec4 o;
vec3 s(vec2 d){ return texture(uTex, vUv + d * uTexel).rgb; }
void main(){
vec3 c = s(vec2(0.0)) * 0.125001
  + (s(vec2(-1.99999, 2.0)) + s(vec2(2.0, 1.99999)) + s(vec2(-2.0, -2.0)) + s(vec2(2.0, -2.00001))) * 0.0312501
  + (s(vec2(0.0, 2.0)) + s(vec2(-1.99999, 0.0)) + s(vec2(2.0, 0.0)) + s(vec2(0.0, -2.00001))) * 0.0624999
  + (s(vec2(-0.99999, 0.99999)) + s(vec2(1.0, 1.00001)) + s(vec2(-1.0, -1.0)) + s(vec2(1.0, -0.99999))) * 0.125;
if (uPre > 0.500001) {
  float br = max(c.r, max(c.g, c.b));
  float k = clamp(br - uThresh * 0.500001, 0.0, uThresh); k = k * k / (2.00001 * uThresh + 1e-5);
  c *= max(k, br - uThresh) / max(br, 1e-5);
}
o = vec4(c, 1.00001);
}`;

const ORB_UP = `#version 300 es
precision highp float;
uniform sampler2D uTex; uniform vec2 uTexel;
in vec2 vUv; out vec4 o;
vec3 s(vec2 d){ return texture(uTex, vUv + d * uTexel).rgb; }
void main(){
vec3 c = s(vec2(0.0)) * 4.0
  + (s(vec2(0.0, 1.00001)) + s(vec2(-1.00001, 0.0)) + s(vec2(0.99999, 0.0)) + s(vec2(0.0, -1.0))) * 2.00001
  + (s(vec2(-1.00001, 1.00001)) + s(vec2(0.99999, 0.99999)) + s(vec2(-0.99999, -1.00001)) + s(vec2(0.99999, -0.99999)));
o = vec4(c / 16.0, 1.0);
}`;

const ORB_COMPOSITE = `#version 300 es
precision highp float;
uniform sampler2D uScene, uBloom; uniform float uBloomK, uExposure, uDec;
in vec2 vUv; out vec4 o;
float hash12(vec2 p){ vec3 p3 = fract(vec3(p.xyx) * 0.1031); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.x + p3.y) * p3.z); }
void main(){
vec4 sc = texture(uScene, vUv);
float fade = 1.0 - smoothstep(0.620001, 0.980001, length(vUv * 1.99999 - 1.00001));
vec3 hdr = (sc.rgb + texture(uBloom, vUv).rgb * uBloomK * fade) * uDec;
vec3 m = 1.00001 - exp(-hdr * uExposure);
float lit = max(m.r, max(m.g, m.b));
m += (hash12(gl_FragCoord.xy) - 0.500001) / 255.0 * smoothstep(0.004, 0.03, lit);
m = max(m, 0.0);
o = vec4(m, clamp(max(sc.a, max(m.r, max(m.g, m.b))), 0.0, 0.99999));
}`;

const hexToRgb = (hex: string): RGB => {
  const h = /^#[0-9a-f]{6}$/i.test(hex) ? hex : '#000000';
  return [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16) / 255) as RGB;
};

interface Prog { p: WebGLProgram; u: Record<string, WebGLUniformLocation | null> }
interface Target { tex: WebGLTexture; fb: WebGLFramebuffer; w: number; h: number }
interface DrawState { time: number; dt: number; level: number; energy: number; spin: number; colors: Colors; steps: number; maxSide: number }

/** Null when WebGL 2 or the shaders are unavailable. */
function createRenderer(cv: HTMLCanvasElement) {
  let gl: WebGL2RenderingContext | null = null;
  try {
    gl = cv.getContext('webgl2', { alpha: true, premultipliedAlpha: true, antialias: false, powerPreference: 'high-performance' });
  } catch {
    gl = null;
  }
  if (!gl) return null;
  const g = gl;
  let res: {
    P: Record<'noise' | 'scene' | 'down' | 'up' | 'comp', Prog>;
    FMT: [number, number];
    enc: number;
    targets: { scene: Target; mips: Target[] } | null;
    key: string;
    noise: WebGLTexture;
  } | null = null;
  let lost = false, adapt = 1, slowFor = 0, fastFor = 0;

  function init() {
    const half = !!g.getExtension('EXT_color_buffer_float');
    const FMT: [number, number] = half ? [g.RGBA16F, g.HALF_FLOAT] : [g.RGBA8, g.UNSIGNED_BYTE];
    const compile = (type: number, src: string) => {
      const s = g.createShader(type)!;
      g.shaderSource(s, src);
      g.compileShader(s);
      if (!g.getShaderParameter(s, g.COMPILE_STATUS)) throw new Error(g.getShaderInfoLog(s) ?? 'shader');
      return s;
    };
    const vs = compile(g.VERTEX_SHADER, ORB_VERT);
    const program = (src: string): Prog => {
      const p = g.createProgram()!;
      g.attachShader(p, vs);
      g.attachShader(p, compile(g.FRAGMENT_SHADER, src));
      g.bindAttribLocation(p, 0, 'a');
      g.linkProgram(p);
      if (!g.getProgramParameter(p, g.LINK_STATUS)) throw new Error(g.getProgramInfoLog(p) ?? 'link');
      const u: Prog['u'] = {};
      const n = g.getProgramParameter(p, g.ACTIVE_UNIFORMS) as number;
      for (let i = 0; i < n; i++) {
        const name = g.getActiveUniform(p, i)!.name;
        u[name] = g.getUniformLocation(p, name);
      }
      return { p, u };
    };
    const P = { noise: program(ORB_NOISE), scene: program(ORB_SCENE), down: program(ORB_DOWN), up: program(ORB_UP), comp: program(ORB_COMPOSITE) };

    g.bindVertexArray(g.createVertexArray());
    g.bindBuffer(g.ARRAY_BUFFER, g.createBuffer());
    g.bufferData(g.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), g.STATIC_DRAW);
    g.enableVertexAttribArray(0);
    g.vertexAttribPointer(0, 2, g.FLOAT, false, 0, 0);

    // Bake the noise volume on the GPU, one slice per draw.
    const N = 96;
    const noise = g.createTexture()!;
    g.bindTexture(g.TEXTURE_3D, noise);
    g.texImage3D(g.TEXTURE_3D, 0, FMT[0], N, N, N, 0, g.RGBA, FMT[1], null);
    for (const [k, v] of [[g.TEXTURE_MIN_FILTER, g.LINEAR], [g.TEXTURE_MAG_FILTER, g.LINEAR], [g.TEXTURE_WRAP_S, g.REPEAT], [g.TEXTURE_WRAP_T, g.REPEAT], [g.TEXTURE_WRAP_R, g.REPEAT]]) g.texParameteri(g.TEXTURE_3D, k, v);
    g.bindFramebuffer(g.FRAMEBUFFER, g.createFramebuffer());
    g.viewport(0, 0, N, N);
    g.useProgram(P.noise.p);
    g.uniform1f(P.noise.u.uN, N);
    g.uniform1f(P.noise.u.uP, 12);
    for (let z = 0; z < N; z++) {
      g.framebufferTextureLayer(g.FRAMEBUFFER, g.COLOR_ATTACHMENT0, noise, 0, z);
      g.uniform1f(P.noise.u.uZ, z);
      g.drawArrays(g.TRIANGLES, 0, 3);
    }
    g.bindFramebuffer(g.FRAMEBUFFER, null);
    res = { P, FMT, enc: half ? 1 : 0.125, targets: null, key: '', noise };
  }

  function target(w: number, h: number): Target {
    const tex = g.createTexture()!;
    g.bindTexture(g.TEXTURE_2D, tex);
    g.texImage2D(g.TEXTURE_2D, 0, res!.FMT[0], w, h, 0, g.RGBA, res!.FMT[1], null);
    for (const [k, v] of [[g.TEXTURE_MIN_FILTER, g.LINEAR], [g.TEXTURE_MAG_FILTER, g.LINEAR], [g.TEXTURE_WRAP_S, g.CLAMP_TO_EDGE], [g.TEXTURE_WRAP_T, g.CLAMP_TO_EDGE]]) g.texParameteri(g.TEXTURE_2D, k, v);
    const fb = g.createFramebuffer()!;
    g.bindFramebuffer(g.FRAMEBUFFER, fb);
    g.framebufferTexture2D(g.FRAMEBUFFER, g.COLOR_ATTACHMENT0, g.TEXTURE_2D, tex, 0);
    return { tex, fb, w, h };
  }
  function ensureTargets(sw: number, sh: number) {
    const key = sw + 'x' + sh;
    if (!res || res.key === key) return;
    if (res.targets) for (const t of [res.targets.scene, ...res.targets.mips]) { g.deleteTexture(t.tex); g.deleteFramebuffer(t.fb); }
    const mips: Target[] = [];
    let w = sw, h = sh;
    for (let i = 0; i < 6 && Math.min(w, h) > 8; i++) { w = Math.max(1, w >> 1); h = Math.max(1, h >> 1); mips.push(target(w, h)); }
    res.targets = { scene: target(sw, sh), mips };
    res.key = key;
  }
  const pass = (prog: Prog, t: Target | null) => {
    g.useProgram(prog.p);
    g.bindFramebuffer(g.FRAMEBUFFER, t ? t.fb : null);
    g.viewport(0, 0, t ? t.w : cv.width, t ? t.h : cv.height);
  };
  const bindTex = (unit: number, tex: WebGLTexture, loc: WebGLUniformLocation | null) => {
    g.activeTexture(g.TEXTURE0 + unit);
    g.bindTexture(g.TEXTURE_2D, tex);
    g.uniform1i(loc, unit);
  };

  const onLost = (e: Event) => { e.preventDefault(); lost = true; res = null; };
  const onRestored = () => { lost = false; try { init(); } catch { res = null; } };
  cv.addEventListener('webglcontextlost', onLost);
  cv.addEventListener('webglcontextrestored', onRestored);
  try { init(); } catch { return null; }

  return {
    draw(s: DrawState): boolean {
      if (lost || !res) return false;
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const W = Math.max(2, Math.round(cv.clientWidth * dpr)), H = Math.max(2, Math.round(cv.clientHeight * dpr));
      if (cv.width !== W || cv.height !== H) { cv.width = W; cv.height = H; }
      // Shrink the ray-traced buffer when frames run long, grow it back with headroom.
      if (s.dt) {
        if (s.dt > 1 / 40) { slowFor += s.dt; fastFor = 0; } else if (s.dt < 1 / 55) { fastFor += s.dt; slowFor = 0; }
        if (slowFor > 0.6 && adapt > 0.5) { adapt = Math.max(0.5, adapt * 0.85); slowFor = 0; }
        if (fastFor > 3 && adapt < 1) { adapt = Math.min(1, adapt * 1.1); fastFor = 0; }
      }
      const scale = Math.min(1, s.maxSide / Math.max(W, H)) * adapt;
      ensureTargets(Math.max(16, Math.round(W * scale)), Math.max(16, Math.round(H * scale)));
      const { P, targets } = res;
      if (!targets) return false;
      g.disable(g.BLEND);

      pass(P.scene, targets.scene);
      const u = P.scene.u;
      g.activeTexture(g.TEXTURE0); g.bindTexture(g.TEXTURE_3D, res.noise); g.uniform1i(u.uNoise, 0);
      g.uniform2f(u.uRes, targets.scene.w, targets.scene.h);
      g.uniform1f(u.uTime, s.time); g.uniform1f(u.uLevel, s.level); g.uniform1f(u.uEnergy, s.energy);
      g.uniform1f(u.uWarm, 0); g.uniform1f(u.uSwirl, 0); g.uniform1f(u.uSpin, s.spin);
      g.uniform1f(u.uDetail, 1); g.uniform1f(u.uLineW, 1); g.uniform1f(u.uCore, 1);
      g.uniform1f(u.uSteps, s.steps); g.uniform1f(u.uEnc, res.enc); g.uniform1f(u.uS, CONFIG.size);
      for (const k of ['Deep', 'Body', 'Glow', 'Plasma', 'Accent', 'Bg'] as const) g.uniform3fv(u['u' + k], s.colors[k]);
      g.drawArrays(g.TRIANGLES, 0, 3);

      // Bloom: downsample with a soft threshold on the first step, then add back up.
      let src = targets.scene;
      targets.mips.forEach((t, i) => {
        pass(P.down, t);
        bindTex(0, src.tex, P.down.u.uTex);
        g.uniform2f(P.down.u.uTexel, 1 / src.w, 1 / src.h);
        g.uniform1f(P.down.u.uPre, i === 0 ? 1 : 0);
        g.uniform1f(P.down.u.uThresh, 0.55 * res!.enc);
        g.drawArrays(g.TRIANGLES, 0, 3);
        src = t;
      });
      g.enable(g.BLEND); g.blendFunc(g.ONE, g.ONE);
      for (let i = targets.mips.length - 2; i >= 0; i--) {
        const from = targets.mips[i + 1];
        pass(P.up, targets.mips[i]);
        bindTex(0, from.tex, P.up.u.uTex);
        g.uniform2f(P.up.u.uTexel, 1 / from.w, 1 / from.h);
        g.drawArrays(g.TRIANGLES, 0, 3);
      }
      g.disable(g.BLEND);

      pass(P.comp, null);
      g.clearColor(0, 0, 0, 0); g.clear(g.COLOR_BUFFER_BIT);
      bindTex(0, targets.scene.tex, P.comp.u.uScene);
      if (targets.mips[0]) bindTex(1, targets.mips[0].tex, P.comp.u.uBloom);
      g.uniform1f(P.comp.u.uBloomK, CONFIG.glow * (1 + 0.6 * s.level));
      g.uniform1f(P.comp.u.uExposure, 1);
      g.uniform1f(P.comp.u.uDec, 1 / res.enc);
      g.drawArrays(g.TRIANGLES, 0, 3);
      return true;
    },
    dispose() {
      cv.removeEventListener('webglcontextlost', onLost);
      cv.removeEventListener('webglcontextrestored', onRestored);
      g.getExtension('WEBGL_lose_context')?.loseContext();
      res = null;
    },
  };
}

interface Props {
  /** Canvas side in CSS px; the glass sphere fills about 55% of it, the glow the rest. */
  size?: number;
  playing?: boolean;
}

export function PlasmaOrb({ size = 64, playing = true }: Props) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const play = useRef(playing);
  const [fallback, setFallback] = useState(false);

  useEffect(() => {
    play.current = playing;
  }, [playing]);

  useEffect(() => {
    const cv = canvas.current;
    if (!cv) return;
    const renderer = createRenderer(cv);
    if (!renderer) {
      setFallback(true);
      return;
    }
    const colors: Colors = {
      Deep: hexToRgb(CONFIG.center), Body: hexToRgb(CONFIG.glass), Glow: hexToRgb(CONFIG.rim),
      Plasma: hexToRgb(CONFIG.plasma), Accent: hexToRgb(CONFIG.accent), Bg: [0, 0, 0],
    };
    const reduced = typeof matchMedia === 'function' ? matchMedia('(prefers-reduced-motion: reduce)') : null;
    const cur = { time: 5.7, spin: 0, level: 0.18 };
    let raf = 0, last = 0, drawnOnce = false;
    const frame = (now: number) => {
      raf = requestAnimationFrame(frame);
      const dt = last ? Math.min(0.05, (now - last) / 1000) : 1 / 60;
      last = now;
      const run = play.current && !reduced?.matches && !document.hidden && document.documentElement.dataset.motion !== 'off';
      if (!run && drawnOnce) return;
      if (run) {
        // a working orb: a little extra energy so it reads as "busy"
        cur.time += dt * CONFIG.speed * (0.55 + CONFIG.energy * 1.1 + cur.level * 1.5);
        cur.spin += dt * CONFIG.speed * 0.04;
      }
      if (renderer.draw({ time: cur.time, dt: run ? dt : 0, level: cur.level, energy: CONFIG.energy, spin: cur.spin, colors, steps: 22, maxSide: 320 })) drawnOnce = true;
    };
    raf = requestAnimationFrame(frame);
    return () => {
      cancelAnimationFrame(raf);
      renderer.dispose();
    };
  }, []);

  return (
    <span className="st-orb" style={{ width: size, height: size }} aria-hidden="true" data-fallback={fallback || undefined}>
      {!fallback && <canvas ref={canvas} style={{ width: size, height: size }} />}
    </span>
  );
}
