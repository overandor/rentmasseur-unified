#!/bin/sh
# Compute sum of 1..16
sum=0
i=1
while [ $i -le 16 ]; do
  sum=$((sum + i))
  i=$((i + 1))
done
echo "sum(1..16) = $sum"
echo "expected = 136"
if [ "$sum" -eq 136 ]; then
  echo 'TASK_COMPLETE'
else
  echo 'TASK_FAILED'
  exit 1
fi
