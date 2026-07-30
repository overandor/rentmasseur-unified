#!/bin/sh
# Compute sum of 1..8
sum=0
i=1
while [ $i -le 8 ]; do
  sum=$((sum + i))
  i=$((i + 1))
done
echo "sum(1..8) = $sum"
echo "expected = 36"
if [ "$sum" -eq 36 ]; then
  echo 'TASK_COMPLETE'
else
  echo 'TASK_FAILED'
  exit 1
fi
