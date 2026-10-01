"use client";

import { useEffect, useRef } from "react";
import { usePathname } from "@/i18n/navigation";
import { useReducedMotion } from "@/lib/use-reduced-motion";

const vertex = `
attribute vec2 position;
void main() { gl_Position = vec4(position, 0.0, 1.0); }
`;
// Original domain-warped contour field: no downloaded textures or reference code.
const fragment = `
precision mediump float;
uniform vec2 resolution;
uniform vec2 pointer;
uniform float time;
uniform float light;
float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float noise(vec2 p) {
  vec2 i = floor(p), f = fract(p);
  f = f * f * (3.0 - 2.0 * f);
  return mix(mix(hash(i), hash(i + vec2(1.,0.)), f.x),
             mix(hash(i + vec2(0.,1.)), hash(i + vec2(1.,1.)), f.x), f.y);
}
float field(vec2 p) {
  float v = 0., a = .5;
  for (int i = 0; i < 4; i++) {
    v += a * noise(p);
    p = mat2(.8, .6, -.6, .8) * p * 2.03 + 2.1;
    a *= .5;
  }
  return v;
}
void main() {
  vec2 uv = gl_FragCoord.xy / resolution;
  vec2 p = (uv - .5) * vec2(resolution.x / resolution.y, 1.) * 3.;
  vec2 m = pointer * vec2(resolution.x / resolution.y, 1.) * 1.5;
  vec2 delta = p - m;
  p += delta * exp(-dot(delta, delta) * .8) * .28;
  float t = time * .045;
  vec2 q = vec2(field(p + t), field(p + vec2(4.2,1.3) - t));
  vec2 r = vec2(field(p + 3.2*q + vec2(1.7,9.2) + t),
                field(p + 3.2*q + vec2(8.3,2.8) - t*.7));
  float f = field(p + 3.8*r);
  float ridge = pow(.5 + .5 * sin(f * 39. + r.x * 6.), 10.);
  float fold = pow(.5 + .5 * sin(f * 20. - q.y * 4.), 3.);
  float shade = .018 + ridge * .115 + fold * .027;
  float vignette = 1. - .35 * length(uv - .5);
  vec3 dark = vec3(shade * .86, shade * .96, shade) * vignette;
  vec3 paper = vec3(.955, .953, .944) - vec3(ridge * .055 + fold * .02);
  gl_FragColor = vec4(mix(dark, paper, light), 1.);
}
`;

export function FluidBackground() {
  const canvas = useRef<HTMLCanvasElement>(null);
  const pathname = usePathname();
  const reduced = useReducedMotion();

  useEffect(() => {
    const element = canvas.current;
    if (!element) return;
    const gl = element.getContext("webgl", {
      alpha: false,
      antialias: false,
      powerPreference: "low-power",
    });
    if (!gl) {
      element.dataset.state = "fallback";
      return;
    }
    const shaders: WebGLShader[] = [];
    const compile = (type: number, source: string) => {
      const shader = gl.createShader(type);
      if (!shader) return null;
      shaders.push(shader);
      gl.shaderSource(shader, source);
      gl.compileShader(shader);
      return gl.getShaderParameter(shader, gl.COMPILE_STATUS) ? shader : null;
    };
    const vs = compile(gl.VERTEX_SHADER, vertex),
      fs = compile(gl.FRAGMENT_SHADER, fragment);
    const program = gl.createProgram();
    const buffer = gl.createBuffer();
    const dispose = () => {
      if (buffer) gl.deleteBuffer(buffer);
      if (program) gl.deleteProgram(program);
      for (const shader of shaders) gl.deleteShader(shader);
    };
    if (!vs || !fs || !program || !buffer) {
      element.dataset.state = "fallback";
      dispose();
      return;
    }
    gl.attachShader(program, vs);
    gl.attachShader(program, fs);
    gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
      element.dataset.state = "fallback";
      dispose();
      return;
    }
    // biome-ignore lint/correctness/useHookAtTopLevel: WebGL useProgram is not a React hook.
    gl.useProgram(program);
    gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
    gl.bufferData(
      gl.ARRAY_BUFFER,
      new Float32Array([-1, -1, 1, -1, -1, 1, -1, 1, 1, -1, 1, 1]),
      gl.STATIC_DRAW,
    );
    const position = gl.getAttribLocation(program, "position");
    gl.enableVertexAttribArray(position);
    gl.vertexAttribPointer(position, 2, gl.FLOAT, false, 0, 0);
    const resolution = gl.getUniformLocation(program, "resolution");
    const mouse = gl.getUniformLocation(program, "pointer");
    const clock = gl.getUniformLocation(program, "time");
    const theme = gl.getUniformLocation(program, "light");
    let frame = 0,
      last = 0,
      elapsed = 0,
      draws = 0,
      paused = false,
      lost = false;
    let px = 0,
      py = 0,
      targetX = 0,
      targetY = 0;
    const stopped = () =>
      reduced ||
      paused ||
      pathname === "/path" ||
      document.hidden ||
      document.documentElement.dataset.motionPaused === "true";
    const draw = () => {
      if (lost) return;
      gl.viewport(0, 0, element.width, element.height);
      gl.uniform2f(resolution, element.width, element.height);
      gl.uniform2f(mouse, px, py);
      element.dataset.pointerX = px.toFixed(3);
      gl.uniform1f(clock, elapsed);
      gl.uniform1f(
        theme,
        document.documentElement.dataset.theme === "light" ? 1 : 0,
      );
      gl.drawArrays(gl.TRIANGLES, 0, 6);
      element.dataset.frame = String(++draws);
    };
    const tick = (now: number) => {
      if (stopped() || lost) {
        frame = 0;
        element.dataset.state = "paused";
        return;
      }
      if (now - last >= 33) {
        elapsed += Math.min(now - last, 66) / 1000;
        last = now;
        px += (targetX - px) * 0.08;
        py += (targetY - py) * 0.08;
        draw();
      }
      frame = requestAnimationFrame(tick);
    };
    const sync = () => {
      if (lost) {
        element.dataset.state = "fallback";
        return;
      }
      cancelAnimationFrame(frame);
      frame = 0;
      last = performance.now();
      draw();
      element.dataset.state = stopped() ? "paused" : "running";
      if (!stopped() && !lost) frame = requestAnimationFrame(tick);
    };
    const resize = () => {
      const scale = Math.min(1, (innerWidth < 768 ? 600 : 1100) / innerWidth);
      element.width = Math.round(innerWidth * scale);
      element.height = Math.round(innerHeight * scale);
      sync();
    };
    const move = (event: PointerEvent) => {
      if (event.pointerType !== "mouse" || stopped()) return;
      targetX = (event.clientX / innerWidth) * 2 - 1;
      targetY = 1 - (event.clientY / innerHeight) * 2;
    };
    const leave = () => {
      targetX = 0;
      targetY = 0;
    };
    const pause = (event: Event) => {
      paused = (event as CustomEvent<boolean>).detail;
      sync();
    };
    const contextLost = (event: Event) => {
      event.preventDefault();
      lost = true;
      cancelAnimationFrame(frame);
      element.dataset.state = "fallback";
    };
    const observer = new MutationObserver(sync);
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["data-theme", "data-motion-paused"],
    });
    window.addEventListener("resize", resize);
    window.addEventListener("pointermove", move, { passive: true });
    window.addEventListener("daari:ambient-pause", pause);
    document.addEventListener("pointerleave", leave);
    document.addEventListener("visibilitychange", sync);
    element.addEventListener("webglcontextlost", contextLost);
    resize();
    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      window.removeEventListener("resize", resize);
      window.removeEventListener("pointermove", move);
      window.removeEventListener("daari:ambient-pause", pause);
      document.removeEventListener("pointerleave", leave);
      document.removeEventListener("visibilitychange", sync);
      element.removeEventListener("webglcontextlost", contextLost);
      dispose();
    };
  }, [pathname, reduced]);

  return (
    <div className="fluid-background" aria-hidden="true">
      <svg
        className="fluid-fallback"
        aria-hidden="true"
        viewBox="0 0 1200 800"
        preserveAspectRatio="xMidYMid slice"
      >
        {[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11].map((band) => (
          <path
            key={band}
            d={`M-100 ${100 + band * 48} C250 ${-150 + band * 44},500 ${900 - band * 30},750 ${350 + band * 20} S1100 ${100 + band * 32},1400 ${650 + band * 28}`}
          />
        ))}
      </svg>
      <canvas ref={canvas} className="fluid-canvas" data-state="initial" />
      <div className="scene-grid" />
    </div>
  );
}
