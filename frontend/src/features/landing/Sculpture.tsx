import { useEffect, useRef } from "react";

const vertex = `attribute vec2 position; void main(){gl_Position=vec4(position,0.,1.);}`;
const fragment = `precision highp float;
uniform vec2 resolution;
uniform vec2 pointer;
uniform float time;
mat2 rot(float a){return mat2(cos(a),-sin(a),sin(a),cos(a));}
vec2 scene(vec3 p){
 p.xz=rot(time*.12+pointer.x*.55)*p.xz;
 p.yz=rot(.25+pointer.y*.35)*p.yz;
 vec3 a=p-vec3(-.52,.20,0.);
 a.xy=rot(-.32)*a.xy;
 float d1=length(vec2(length(a.xy)-.91,a.z))-.255;
 vec3 b=p-vec3(.52,-.20,0.);
 b.xz=rot(1.12)*b.xz;
 b.xy=rot(.32)*b.xy;
 float d2=length(vec2(length(b.xy)-.91,b.z))-.255;
 return d1<d2?vec2(d1,0.):vec2(d2,1.);
}
vec3 normal(vec3 p){vec2 e=vec2(.001,0.);return normalize(vec3(scene(p+e.xyy).x-scene(p-e.xyy).x,scene(p+e.yxy).x-scene(p-e.yxy).x,scene(p+e.yyx).x-scene(p-e.yyx).x));}
void main(){
 vec2 uv=(gl_FragCoord.xy*2.-resolution)/resolution.y;
 uv*=max(1.,resolution.y/resolution.x*1.05);
 vec3 ro=vec3(0.,0.,5.2),rd=normalize(vec3(uv,-3.3));
 vec3 col=mix(vec3(.91,.88,.82),vec3(.965,.948,.912),gl_FragCoord.y/resolution.y);
 float shadow=exp(-pow(uv.x*1.1,2.)-pow((uv.y+.98)*7.,2.));
 col-=shadow*.17;
 float depth=0.;vec2 hit=vec2(0.);
 for(int i=0;i<76;i++){hit=scene(ro+rd*depth);if(hit.x<.0015||depth>9.)break;depth+=hit.x*.85;}
 if(depth<9.){
 vec3 p=ro+rd*depth,n=normal(p),l=normalize(vec3(-3.,5.,5.));
 vec3 base=mix(vec3(.64,.51,.33),vec3(.25,.025,.065),hit.y);
 float diff=max(dot(n,l),0.);
 float spec=pow(max(dot(reflect(-l,n),-rd),0.),38.);
 float fres=pow(1.-max(dot(n,-rd),0.),3.);
 float ao=clamp(scene(p+n*.15).x/.15,.35,1.);
 col=base*(.4+diff*.8)*ao+vec3(1.,.91,.74)*spec*.85+vec3(.55,.43,.32)*fres*.32;
 col+=pow(max(dot(n,normalize(vec3(3.,1.,-2.))),0.),4.)*.12;
 }
 float grain=fract(sin(dot(gl_FragCoord.xy,vec2(12.9898,78.233)))*43758.5453)-.5;
 gl_FragColor=vec4(pow(max(col,0.),vec3(.88))+grain*.012,1.);
}`;

export function Sculpture() {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const canvas = ref.current!;
    const gl = canvas.getContext("webgl", {
      alpha: false,
      antialias: false,
      powerPreference: "low-power",
    });
    if (!gl) return;
    const shader = (type: number, source: string) => {
      const item = gl.createShader(type)!;
      gl.shaderSource(item, source);
      gl.compileShader(item);
      if (!gl.getShaderParameter(item, gl.COMPILE_STATUS)) {
        gl.deleteShader(item);
        return null;
      }
      return item;
    };
    const vs = shader(gl.VERTEX_SHADER, vertex),
      fs = shader(gl.FRAGMENT_SHADER, fragment);
    if (!vs || !fs) return;
    const program = gl.createProgram()!;
    gl.attachShader(program, vs);
    gl.attachShader(program, fs);
    gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) return;
    gl.useProgram(program);
    const buffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
    gl.bufferData(
      gl.ARRAY_BUFFER,
      new Float32Array([-1, -1, 1, -1, -1, 1, -1, 1, 1, -1, 1, 1]),
      gl.STATIC_DRAW,
    );
    const pos = gl.getAttribLocation(program, "position");
    gl.enableVertexAttribArray(pos);
    gl.vertexAttribPointer(pos, 2, gl.FLOAT, false, 0, 0);
    const res = gl.getUniformLocation(program, "resolution"),
      mouse = gl.getUniformLocation(program, "pointer"),
      clock = gl.getUniformLocation(program, "time");
    const reduced = matchMedia("(prefers-reduced-motion: reduce)");
    let frame = 0,
      visible = true,
      last = 0,
      elapsed = 0,
      x = 0,
      y = 0,
      targetX = 0,
      targetY = 0;
    const draw = () => {
      gl.viewport(0, 0, canvas.width, canvas.height);
      gl.uniform2f(res, canvas.width, canvas.height);
      gl.uniform2f(mouse, x, y);
      gl.uniform1f(clock, elapsed);
      gl.drawArrays(gl.TRIANGLES, 0, 6);
      canvas.dataset.ready = "true";
    };
    const animate = (now: number) => {
      frame = 0;
      if (!visible || document.hidden || reduced.matches) return;
      if (last && now - last < 1000 / 30) {
        frame = requestAnimationFrame(animate);
        return;
      }
      elapsed += last ? Math.min((now - last) / 1000, 0.05) : 0;
      last = now;
      x += (targetX - x) * 0.08;
      y += (targetY - y) * 0.08;
      draw();
      frame = requestAnimationFrame(animate);
    };
    const schedule = () => {
      cancelAnimationFrame(frame);
      last = 0;
      if (visible && !document.hidden && !reduced.matches)
        frame = requestAnimationFrame(animate);
      else draw();
    };
    const resize = new ResizeObserver(() => {
      const r = canvas.getBoundingClientRect();
      const scale = Math.min(devicePixelRatio, 1.25);
      canvas.width = Math.max(1, Math.round(r.width * scale));
      canvas.height = Math.max(1, Math.round(r.height * scale));
      draw();
    });
    resize.observe(canvas);
    const observer = new IntersectionObserver(([entry]) => {
      visible = entry.isIntersecting;
      schedule();
    });
    observer.observe(canvas);
    const move = (event: PointerEvent) => {
      if (reduced.matches || event.pointerType === "touch") return;
      const r = canvas.getBoundingClientRect();
      targetX = Math.max(
        -1,
        Math.min(1, ((event.clientX - r.left) / r.width) * 2 - 1),
      );
      targetY = Math.max(
        -1,
        Math.min(1, ((event.clientY - r.top) / r.height) * 2 - 1),
      );
    };
    const reset = () => {
      targetX = 0;
      targetY = 0;
    };
    canvas.addEventListener("pointermove", move);
    canvas.addEventListener("pointerleave", reset);
    document.addEventListener("visibilitychange", schedule);
    reduced.addEventListener("change", schedule);
    schedule();
    return () => {
      cancelAnimationFrame(frame);
      resize.disconnect();
      observer.disconnect();
      canvas.removeEventListener("pointermove", move);
      canvas.removeEventListener("pointerleave", reset);
      document.removeEventListener("visibilitychange", schedule);
      reduced.removeEventListener("change", schedule);
      gl.deleteBuffer(buffer);
      gl.deleteProgram(program);
      gl.deleteShader(vs);
      gl.deleteShader(fs);
    };
  }, []);
  return (
    <div className="sculpture-fallback">
      <div className="fallback-ring" />
      <canvas ref={ref} className="sculpture-canvas" aria-hidden="true" />
    </div>
  );
}
