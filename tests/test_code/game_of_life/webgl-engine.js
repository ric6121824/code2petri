class WebGLEngine {
    constructor(canvas, width, height) {
        this.canvas = canvas;
        this.gl = canvas.getContext('webgl2');
        if (!this.gl) {
            alert('WebGL2 not supported');
            return;
        }

        this.width = width;
        this.height = height;

        this.initShaders();
        this.initBuffers();
    }

    initShaders() {
        const gl = this.gl;

        const vsSource = `#version 300 es
        in vec4 a_position;
        out vec2 v_texCoord;
        void main() {
            gl_Position = a_position;
            v_texCoord = a_position.xy * 0.5 + 0.5; // Map [-1,1] to [0,1]
        }`;

        const fsSource = `#version 300 es
        precision highp float;
        
        uniform sampler2D u_state;
        uniform vec2 u_texSize;
        
        in vec2 v_texCoord;
        out vec4 outColor;
        
        int get(int x, int y) {
            vec2 offset = vec2(x, y) / u_texSize;
            return int(texture(u_state, v_texCoord + offset).r);
        }
        
        void main() {
            int currentState = get(0, 0);
            
            // Texture Graphic Offsets (Simultaneous evaluation of neighbors)
            int neighbors = 
                get(-1, -1) + get(0, -1) + get(1, -1) +
                get(-1,  0) +              get(1,  0) +
                get(-1,  1) + get(0,  1) + get(1,  1);
                
            int nextState = currentState;
            if (currentState == 1 && (neighbors < 2 || neighbors > 3)) {
                nextState = 0;
            } else if (currentState == 0 && neighbors == 3) {
                nextState = 1;
            }
            
            // Output state in the red channel
            outColor = vec4(float(nextState), 0.0, 0.0, 1.0);
        }`;

        // Create display shader (maps state 1/0 to neon colors)
        const fsDisplaySource = `#version 300 es
        precision highp float;
        
        uniform sampler2D u_state;
        
        in vec2 v_texCoord;
        out vec4 outColor;
        
        void main() {
            float state = texture(u_state, v_texCoord).r;
            // Neon cyan for alive (0, 240, 255), dark blue for dead
            if(state > 0.5) {
                outColor = vec4(0.0, 0.94, 1.0, 1.0);
            } else {
                outColor = vec4(0.1, 0.13, 0.21, 1.0);
            }
        }`;

        this.computeProgram = this.createProgram(vsSource, fsSource);
        this.displayProgram = this.createProgram(vsSource, fsDisplaySource);

        // Setup fullscreen quad
        const positionBuffer = gl.createBuffer();
        gl.bindBuffer(gl.ARRAY_BUFFER, positionBuffer);
        gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([
            -1, -1,
             1, -1,
            -1,  1,
            -1,  1,
             1, -1,
             1,  1,
        ]), gl.STATIC_DRAW);

        this.positionLocationCompute = gl.getAttribLocation(this.computeProgram, "a_position");
        this.positionLocationDisplay = gl.getAttribLocation(this.displayProgram, "a_position");
    }

    createProgram(vsSource, fsSource) {
        const gl = this.gl;
        const vs = gl.createShader(gl.VERTEX_SHADER);
        gl.shaderSource(vs, vsSource);
        gl.compileShader(vs);
        
        const fs = gl.createShader(gl.FRAGMENT_SHADER);
        gl.shaderSource(fs, fsSource);
        gl.compileShader(fs);
        
        const prog = gl.createProgram();
        gl.attachShader(prog, vs);
        gl.attachShader(prog, fs);
        gl.linkProgram(prog);
        return prog;
    }

    createTexture() {
        const gl = this.gl;
        const tex = gl.createTexture();
        gl.bindTexture(gl.TEXTURE_2D, tex);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.NEAREST);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.NEAREST);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.REPEAT);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.REPEAT);
        // Ensure R8 format for single channel integer-like state
        gl.texImage2D(gl.TEXTURE_2D, 0, gl.R8, this.width, this.height, 0, gl.RED, gl.UNSIGNED_BYTE, null);
        return tex;
    }

    initBuffers() {
        const gl = this.gl;
        
        // Two textures for ping-ponging
        this.texA = this.createTexture();
        this.texB = this.createTexture();

        // Two framebuffers
        this.fbA = gl.createFramebuffer();
        gl.bindFramebuffer(gl.FRAMEBUFFER, this.fbA);
        gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, this.texA, 0);

        this.fbB = gl.createFramebuffer();
        gl.bindFramebuffer(gl.FRAMEBUFFER, this.fbB);
        gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, this.texB, 0);

        // Set initial read/write states
        this.readTex = this.texA;
        this.writeFb = this.fbB;
        this.writeTex = this.texB;
    }

    randomize() {
        const gl = this.gl;
        const data = new Uint8Array(this.width * this.height);
        for(let i=0; i<data.length; i++) {
            data[i] = Math.random() > 0.8 ? 255 : 0;
        }
        
        gl.bindTexture(gl.TEXTURE_2D, this.readTex);
        gl.texSubImage2D(gl.TEXTURE_2D, 0, 0, 0, this.width, this.height, gl.RED, gl.UNSIGNED_BYTE, data);
        this.drawToScreen();
    }

    step() {
        const gl = this.gl;

        // 1. Compute Step (Render to texture)
        gl.useProgram(this.computeProgram);
        gl.bindFramebuffer(gl.FRAMEBUFFER, this.writeFb);
        gl.viewport(0, 0, this.width, this.height);

        gl.enableVertexAttribArray(this.positionLocationCompute);
        gl.vertexAttribPointer(this.positionLocationCompute, 2, gl.FLOAT, false, 0, 0);

        gl.activeTexture(gl.TEXTURE0);
        gl.bindTexture(gl.TEXTURE_2D, this.readTex);
        
        const stateLoc = gl.getUniformLocation(this.computeProgram, "u_state");
        const sizeLoc = gl.getUniformLocation(this.computeProgram, "u_texSize");
        gl.uniform1i(stateLoc, 0);
        gl.uniform2f(sizeLoc, this.width, this.height);

        gl.drawArrays(gl.TRIANGLES, 0, 6);

        // Ping-pong
        let tempTex = this.readTex;
        this.readTex = this.writeTex;
        this.writeTex = tempTex;

        let tempFb = this.fbA === this.writeFb ? this.fbB : this.fbA;
        this.writeFb = tempFb;

        // 2. Display Step (Render texture to screen)
        this.drawToScreen();
    }

    drawToScreen() {
        const gl = this.gl;
        
        gl.useProgram(this.displayProgram);
        gl.bindFramebuffer(gl.FRAMEBUFFER, null); // screen
        gl.viewport(0, 0, this.canvas.width, this.canvas.height);

        gl.enableVertexAttribArray(this.positionLocationDisplay);
        gl.vertexAttribPointer(this.positionLocationDisplay, 2, gl.FLOAT, false, 0, 0);

        gl.activeTexture(gl.TEXTURE0);
        gl.bindTexture(gl.TEXTURE_2D, this.readTex);

        const stateLoc = gl.getUniformLocation(this.displayProgram, "u_state");
        gl.uniform1i(stateLoc, 0);

        gl.drawArrays(gl.TRIANGLES, 0, 6);
    }
}
