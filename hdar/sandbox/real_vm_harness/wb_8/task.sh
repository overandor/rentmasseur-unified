#!/bin/sh
# Compute sum of 1..1
sum=0
i=1
while [ $i -le 1 ]; do
  sum=$((sum + i))
  i=$((i + 1))
done
echo "sum(1..1) = $sum"
echo "expected = 1"
if [ "$sum" -eq 1 ]; then
  echo 'TASK_COMPLETE'
else
  echo 'TASK_FAILED'
  exit 1
fi
