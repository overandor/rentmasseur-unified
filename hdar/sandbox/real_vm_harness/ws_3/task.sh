#!/bin/sh
# Compute sum of 1..29
sum=0
i=1
while [ $i -le 29 ]; do
  sum=$((sum + i))
  i=$((i + 1))
done
echo "sum(1..29) = $sum"
echo "expected = 435"
if [ "$sum" -eq 435 ]; then
  echo 'TASK_COMPLETE'
else
  echo 'TASK_FAILED'
  exit 1
fi
