"use strict";

(() => {
  const panel = document.getElementById("studio-panel");
  const canvas = document.getElementById("studio-canvas");
  const select = document.getElementById("scene-select");
  const description = document.getElementById("scene-description");
  const status = document.getElementById("studio-status");
  const vrButton = document.getElementById("vr-button");
  const arButton = document.getElementById("ar-button");
  const exitButton = document.getElementById("xr-exit");
  const descriptions = {
    avatar: "An abstract animated visual for Priya, not a physical hologram.",
    atom: "A stylized atom: electrons and the nucleus are illustrated, not shown to scale.",
    water: "A simplified water molecule: one oxygen atom and two hydrogen atoms.",
    solar: "A simplified solar system. Planet sizes, distances, and speeds are not to scale.",
  };
  let session = null;
  let rotationX = -0.15;
  let rotationY = 0.3;
  let dragging = false;
  let lastX = 0;
  let lastY = 0;
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const gl = canvas.getContext("webgl", { alpha: true, antialias: true, xrCompatible: true });

  function setScene(scene) {
    if (!Object.hasOwn(descriptions, scene)) return;
    select.value = scene;
    description.textContent = descriptions[scene];
  }
  select.addEventListener("change", () => setScene(select.value));
  window.addEventListener("priya-open-studio", (event) => {
    setScene(event.detail);
    window.dispatchEvent(new CustomEvent("priya-open-panel", { detail: "studio-panel" }));
  });
  window.addEventListener("priya-panel-changed", (event) => {
    if (event.detail !== "studio-panel" && session) session.end().catch((error) => {
      status.textContent = `Could not end immersive mode: ${error.message}`;
    });
  });
  setScene("avatar");

  if (!gl) {
    status.textContent = "3D is unavailable because this browser could not start WebGL.";
    return;
  }

  function shader(type, source) {
    const result = gl.createShader(type);
    gl.shaderSource(result, source);
    gl.compileShader(result);
    if (!gl.getShaderParameter(result, gl.COMPILE_STATUS)) {
      const message = gl.getShaderInfoLog(result);
      gl.deleteShader(result);
      throw new Error(message || "Shader compilation failed.");
    }
    return result;
  }

  let program;
  try {
    program = gl.createProgram();
    gl.attachShader(program, shader(gl.VERTEX_SHADER, `
      attribute vec3 position;
      attribute vec3 normal;
      uniform mat4 matrix;
      varying vec3 vNormal;
      void main() { vNormal = normal; gl_Position = matrix * vec4(position, 1.0); }
    `));
    gl.attachShader(program, shader(gl.FRAGMENT_SHADER, `
      precision mediump float;
      uniform vec4 color;
      uniform float glow;
      varying vec3 vNormal;
      void main() {
        float light = 0.4 + 0.6 * max(dot(normalize(vNormal), normalize(vec3(0.5, 0.8, 1.0))), 0.0);
        gl_FragColor = vec4(color.rgb * mix(light, 1.0, glow), color.a);
      }
    `));
    gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(program));
  } catch (error) {
    status.textContent = `3D could not be initialized: ${error.message}`;
    return;
  }

  const position = gl.getAttribLocation(program, "position");
  const normal = gl.getAttribLocation(program, "normal");
  const matrixLocation = gl.getUniformLocation(program, "matrix");
  const colorLocation = gl.getUniformLocation(program, "color");
  const glowLocation = gl.getUniformLocation(program, "glow");

  function buffer(vertices, mode) {
    const bufferObject = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, bufferObject);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(vertices), gl.STATIC_DRAW);
    return { buffer: bufferObject, count: vertices.length / 6, mode };
  }
  function sphereMesh() {
    const vertices = [];
    const point = (lat, lon) => {
      const phi = Math.PI * lat / 14;
      const theta = 2 * Math.PI * lon / 20;
      return [Math.sin(phi) * Math.cos(theta), Math.cos(phi), Math.sin(phi) * Math.sin(theta)];
    };
    const put = (p) => vertices.push(...p, ...p);
    for (let lat = 0; lat < 14; lat++) {
      for (let lon = 0; lon < 20; lon++) {
        const a = point(lat, lon), b = point(lat + 1, lon), c = point(lat + 1, lon + 1), d = point(lat, lon + 1);
        put(a); put(b); put(c); put(a); put(c); put(d);
      }
    }
    return buffer(vertices, gl.TRIANGLES);
  }
  function ringMesh() {
    const vertices = [];
    for (let i = 0; i < 128; i++) {
      for (const angle of [2 * Math.PI * i / 128, 2 * Math.PI * (i + 1) / 128]) {
        vertices.push(Math.cos(angle), Math.sin(angle), 0, 0, 0, 1);
      }
    }
    return buffer(vertices, gl.LINES);
  }
  function lineMesh() {
    return buffer([0, 0, 0, 0, 0, 1, 1, 0, 0, 0, 0, 1], gl.LINES);
  }
  const sphere = sphereMesh(), ring = ringMesh(), line = lineMesh();

  function identity() { return new Float32Array([1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]); }
  function multiply(a, b) {
    const out = new Float32Array(16);
    for (let col = 0; col < 4; col++) for (let row = 0; row < 4; row++) {
      for (let k = 0; k < 4; k++) out[col * 4 + row] += a[k * 4 + row] * b[col * 4 + k];
    }
    return out;
  }
  function translate(x, y, z) { const m = identity(); m[12] = x; m[13] = y; m[14] = z; return m; }
  function scale(x, y = x, z = x) { const m = identity(); m[0] = x; m[5] = y; m[10] = z; return m; }
  function rotateX(angle) {
    const m = identity(), c = Math.cos(angle), s = Math.sin(angle);
    m[5] = c; m[6] = s; m[9] = -s; m[10] = c; return m;
  }
  function rotateY(angle) {
    const m = identity(), c = Math.cos(angle), s = Math.sin(angle);
    m[0] = c; m[2] = -s; m[8] = s; m[10] = c; return m;
  }
  function rotateZ(angle) {
    const m = identity(), c = Math.cos(angle), s = Math.sin(angle);
    m[0] = c; m[1] = s; m[4] = -s; m[5] = c; return m;
  }
  function perspective(aspect) {
    const f = 1 / Math.tan(Math.PI / 7), near = 0.1, far = 100;
    const m = new Float32Array(16);
    m[0] = f / aspect; m[5] = f; m[10] = (far + near) / (near - far);
    m[11] = -1; m[14] = 2 * far * near / (near - far);
    return m;
  }

  function drawMesh(mesh, projectionView, model, color, glow = 0) {
    gl.bindBuffer(gl.ARRAY_BUFFER, mesh.buffer);
    gl.vertexAttribPointer(position, 3, gl.FLOAT, false, 24, 0);
    gl.vertexAttribPointer(normal, 3, gl.FLOAT, false, 24, 12);
    gl.uniformMatrix4fv(matrixLocation, false, multiply(projectionView, model));
    gl.uniform4fv(colorLocation, color);
    gl.uniform1f(glowLocation, glow);
    gl.drawArrays(mesh.mode, 0, mesh.count);
  }
  function drawScene(projectionView, root, seconds) {
    const dot = (x, y, z, radius, color, glow = 0) => {
      drawMesh(sphere, projectionView, multiply(root, multiply(translate(x, y, z), scale(radius))), color, glow);
    };
    const orbit = (radius, tilt, spin, color) => {
      const transform = multiply(rotateZ(spin), multiply(rotateX(tilt), scale(radius)));
      drawMesh(ring, projectionView, multiply(root, transform), color, 1);
    };
    if (select.value === "avatar") {
      dot(0, 0, 0, 0.56 + (reduceMotion ? 0 : 0.025 * Math.sin(seconds * 2)), [0.35, 0.66, 1, 0.9], 0.35);
      for (let i = 0; i < 4; i++) orbit(0.92 + i * 0.16, 0.45 + i * 0.46, seconds * (i % 2 ? -0.13 : 0.13), [0.35, 0.75, 1, 0.48]);
      for (let i = 0; i < 12; i++) {
        const a = i * Math.PI / 6 + seconds * 0.3;
        dot(1.48 * Math.cos(a), 0.65 * Math.sin(a * 2), 0.6 * Math.sin(a), 0.035, [0.65, 0.95, 1, 0.9], 1);
      }
    } else if (select.value === "atom") {
      dot(-0.12, 0.06, 0, 0.25, [0.95, 0.48, 0.65, 1]);
      dot(0.12, -0.06, 0, 0.25, [0.47, 0.65, 1, 1]);
      for (let i = 0; i < 3; i++) {
        const tilt = 0.7 + i * 0.6, spin = i * Math.PI / 3;
        orbit(1.35, tilt, spin, [0.35, 0.72, 1, 0.5]);
        const a = seconds * (0.8 + i * 0.2) + i * 2;
        const transform = multiply(rotateZ(spin), rotateX(tilt));
        const x = 1.35 * Math.cos(a), y = 1.35 * Math.sin(a);
        dot(transform[0] * x + transform[4] * y, transform[1] * x + transform[5] * y, transform[2] * x + transform[6] * y, 0.095, [0.53, 0.94, 1, 1], 0.6);
      }
    } else if (select.value === "water") {
      dot(0, 0, 0, 0.55, [0.98, 0.36, 0.53, 1]);
      for (const x of [-0.95, 0.95]) {
        const y = -0.68;
        const bond = multiply(translate(0, 0, 0), multiply(rotateZ(Math.atan2(y, x)), scale(Math.hypot(x, y), 1, 1)));
        drawMesh(line, projectionView, multiply(root, bond), [0.78, 0.88, 1, 1], 1);
        dot(x, y, 0, 0.34, [0.68, 0.85, 1, 1]);
      }
    } else {
      dot(0, 0, 0, 0.31, [1, 0.72, 0.3, 1], 0.6);
      const colors = [[0.7,0.7,0.8,1],[0.9,0.72,0.48,1],[0.36,0.67,1,1],[0.9,0.42,0.35,1],[0.86,0.72,0.58,1],[0.85,0.79,0.6,1],[0.48,0.82,0.88,1],[0.4,0.55,0.98,1]];
      for (let i = 0; i < 8; i++) {
        const radius = 0.47 + i * 0.16, angle = seconds * (0.6 / (i + 1)) + i * 0.9;
        orbit(radius, 1.3, 0, [0.36, 0.58, 0.85, 0.35]);
        dot(radius * Math.cos(angle), radius * Math.sin(angle) * Math.cos(1.3), radius * Math.sin(angle) * Math.sin(1.3), i > 3 ? 0.11 : 0.07, colors[i]);
      }
    }
  }
  gl.useProgram(program);
  gl.enableVertexAttribArray(position);
  gl.enableVertexAttribArray(normal);
  gl.enable(gl.DEPTH_TEST);
  gl.enable(gl.BLEND);
  gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);

  function desktopFrame(time) {
    requestAnimationFrame(desktopFrame);
    if (panel.hidden || session || gl.isContextLost()) return;
    const ratio = Math.min(window.devicePixelRatio || 1, 2);
    const width = Math.max(1, Math.round(canvas.clientWidth * ratio));
    const height = Math.max(1, Math.round(canvas.clientHeight * ratio));
    if (canvas.width !== width || canvas.height !== height) { canvas.width = width; canvas.height = height; }
    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    gl.viewport(0, 0, width, height);
    gl.clearColor(0, 0, 0, 0);
    gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
    const t = reduceMotion ? 0 : time / 1000;
    const projectionView = multiply(perspective(width / height), translate(0, 0, -4.7));
    const root = multiply(rotateX(rotationX), rotateY(rotationY + t * 0.08));
    drawScene(projectionView, root, t);
  }
  requestAnimationFrame(desktopFrame);

  canvas.addEventListener("pointerdown", (event) => {
    dragging = true; lastX = event.clientX; lastY = event.clientY; canvas.setPointerCapture(event.pointerId);
  });
  canvas.addEventListener("pointermove", (event) => {
    if (!dragging) return;
    rotationY += (event.clientX - lastX) * 0.01;
    rotationX += (event.clientY - lastY) * 0.01;
    lastX = event.clientX; lastY = event.clientY;
  });
  canvas.addEventListener("pointerup", () => { dragging = false; });
  canvas.addEventListener("pointercancel", () => { dragging = false; });
  canvas.addEventListener("webglcontextlost", (event) => {
    event.preventDefault();
    status.textContent = "The 3D graphics context was lost. Reload the page to try again.";
  });

  async function checkXR() {
    if (!navigator.xr || !window.isSecureContext) {
      status.textContent = "AR/VR requires a secure context, a compatible browser, and a headset or AR device.";
      return;
    }
    try {
      const [vr, ar] = await Promise.all([
        navigator.xr.isSessionSupported("immersive-vr"), navigator.xr.isSessionSupported("immersive-ar"),
      ]);
      vrButton.hidden = !vr;
      arButton.hidden = !ar;
      status.textContent = vr || ar ? "Compatible immersive device detected." : "No compatible immersive device detected. The 3D view still works on this screen.";
    } catch (error) {
      status.textContent = `Could not check AR/VR support: ${error.message}`;
    }
  }
  async function enterXR(mode) {
    let startedSession = null;
    try {
      startedSession = await navigator.xr.requestSession(mode);
      if (panel.hidden) {
        await startedSession.end();
        return;
      }
      await gl.makeXRCompatible();
      const reference = await startedSession.requestReferenceSpace("local");
      startedSession.updateRenderState({ baseLayer: new XRWebGLLayer(startedSession, gl, { alpha: true }) });
      session = startedSession;
      exitButton.hidden = false;
      vrButton.hidden = true;
      arButton.hidden = true;
      status.textContent = mode === "immersive-ar" ? "AR session active." : "VR session active.";
      startedSession.addEventListener("end", () => {
        session = null;
        exitButton.hidden = true;
        checkXR();
      }, { once: true });
      const frameLoop = (time, frame) => {
        if (session !== startedSession) return;
        const pose = frame.getViewerPose(reference);
        const layer = startedSession.renderState.baseLayer;
        gl.bindFramebuffer(gl.FRAMEBUFFER, layer.framebuffer);
        gl.clearColor(0.02, 0.04, 0.08, mode === "immersive-ar" ? 0 : 1);
        gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
        if (pose) for (const view of pose.views) {
          const viewport = layer.getViewport(view);
          gl.viewport(viewport.x, viewport.y, viewport.width, viewport.height);
          const projectionView = multiply(view.projectionMatrix, view.transform.inverse.matrix);
          const t = reduceMotion ? 0 : time / 1000;
          const root = multiply(translate(0, 0, -2.5), multiply(scale(0.6), multiply(rotateX(rotationX), rotateY(rotationY + t * 0.08))));
          drawScene(projectionView, root, t);
        }
        startedSession.requestAnimationFrame(frameLoop);
      };
      startedSession.requestAnimationFrame(frameLoop);
    } catch (error) {
      if (startedSession) {
        try { await startedSession.end(); } catch (endError) { console.error("Could not end AR/VR session:", endError); }
      }
      session = null;
      exitButton.hidden = true;
      status.textContent = `Could not start AR/VR: ${error.message}`;
    }
  }
  vrButton.addEventListener("click", () => enterXR("immersive-vr"));
  arButton.addEventListener("click", () => enterXR("immersive-ar"));
  exitButton.addEventListener("click", () => {
    if (session) session.end().catch((error) => { status.textContent = `Could not end AR/VR: ${error.message}`; });
  });
  checkXR();
})();
