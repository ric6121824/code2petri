#!/bin/bash
set -x

APP_JS="/Users/pingchungtsai/My Drive (ric6121824@gmail.com)/Digital Media MSc/Semester 4/GameOfLife_Simulator/app.js"
WEBGL_JS="/Users/pingchungtsai/My Drive (ric6121824@gmail.com)/Digital Media MSc/Semester 4/GameOfLife_Simulator/webgl-engine.js"
OUT_DIR=".scratch/code2petri/graphs/GameOfLife-260911"

run_gen() {
    local src="$1"
    local func="$2"
    local ctx="$3"
    local outname="$4"
    
    echo "Processing $outname..."
    for ext in dot svg png pnml json; do
        python3 -m code2petri.engine "$src" -t "$func" --context "$ctx" -o "$OUT_DIR/${outname}.${ext}"
    done
}

run_gen "$APP_JS" "loop" "$WEBGL_JS" "app_loop"
run_gen "$APP_JS" "randomizeBoth" "$WEBGL_JS" "app_randomizeBoth"
run_gen "$APP_JS" "stepCpu" "$WEBGL_JS" "app_stepCpu"
run_gen "$APP_JS" "init" "$WEBGL_JS" "app_init"
run_gen "$APP_JS" "(global)" "$WEBGL_JS" "app_global"

run_gen "$WEBGL_JS" "WebGLEngine.step" "$APP_JS" "webgl_step"
run_gen "$WEBGL_JS" "WebGLEngine.randomize" "$APP_JS" "webgl_randomize"
run_gen "$WEBGL_JS" "WebGLEngine.drawToScreen" "$APP_JS" "webgl_drawToScreen"
run_gen "$WEBGL_JS" "WebGLEngine.constructor" "$APP_JS" "webgl_constructor"
