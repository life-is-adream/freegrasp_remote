#!/bin/bash
set -e
cd /home/public/zb/FreeGrasp_code-freegrasp_codex

export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export PYTHONUNBUFFERED=1

RUN_ROOT="/home/public/zb/FreeGrasp_code-main/data/output/freegrasp_codex_v10_full_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$RUN_ROOT"

echo "结果目录：$RUN_ROOT"
echo "开始时间：$(date)"

.venv/bin/python -u evaluate_mimo_full_protocol.py \
  --model-name mimo-v2.5 \
  --max-output-tokens 1024 \
  --subset-policy hard_blocker_first_v10 \
  --run-root "$RUN_ROOT" \
  --splits 0 1 2 \
  --reuse-molmo \
  --no-resume \
  --skip-mimo-preflight \
  > "$RUN_ROOT/run.log" 2>&1 &

PID=$!
echo $PID | tee "$RUN_ROOT/pid"
echo "进程PID：$PID"
echo "正在后台运行，日志：$RUN_ROOT/run.log"

# 等待几秒检查进程是否正常启动
sleep 3
if kill -0 $PID 2>/dev/null; then
    echo "✅ 进程已正常启动"
else
    echo "❌ 进程启动失败，请检查日志"
    cat "$RUN_ROOT/run.log"
fi
