#!/bin/sh
# Compute sum of 1..70
sum=0
i=1
while [ $i -le 70 ]; do
  sum=$((sum + i))
  i=$((i + 1))
done
echo "sum(1..70) = $sum"
echo "expected = 2485"
if [ "$sum" -eq 2485 ]; then
  echo 'TASK_COMPLETE'
else
  echo 'TASK_FAILED'
  exit 1
fi
