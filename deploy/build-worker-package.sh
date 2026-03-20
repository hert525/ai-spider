#!/bin/bash
# 打包Worker精简包
set -e

cd /root/.openclaw/workspace/ai-spider

OUTFILE="deploy/worker-package.tar.gz"

# 创建临时目录来组织文件
TMPDIR=$(mktemp -d)
trap "rm -rf $TMPDIR" EXIT

# 复制需要的文件
cp worker.py "$TMPDIR/"
cp deploy/requirements-worker.txt "$TMPDIR/"
cp .env.example "$TMPDIR/" 2>/dev/null || echo "# AI Spider Worker Config" > "$TMPDIR/.env.example"

# 复制src（排除不需要的）
rsync -a --exclude='__pycache__' --exclude='*.pyc' \
    --exclude='web/' --exclude='api/' \
    src/ "$TMPDIR/src/"

# Worker也需要最小的api stub（避免import报错），创建空的
mkdir -p "$TMPDIR/src/api" "$TMPDIR/src/api/v1"
echo '"""API stub for worker."""' > "$TMPDIR/src/api/__init__.py"
echo '"""V1 stub."""' > "$TMPDIR/src/api/v1/__init__.py"

# 打包
cd "$TMPDIR"
tar czf "/root/.openclaw/workspace/ai-spider/$OUTFILE" .

echo "✅ Worker包已生成: $OUTFILE ($(du -h /root/.openclaw/workspace/ai-spider/$OUTFILE | cut -f1))"
