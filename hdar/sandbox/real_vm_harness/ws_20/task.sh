#!/bin/sh
# Compute sum of 1..65
sum=0
i=1
while [ $i -le 65 ]; do
  sum=$((sum + i))
  i=$((i + 1))
done
echo "sum(1..65) = $sum"
echo "expected = 2145"
if [ "$sum" -eq 2145 ]; then
  echo 'TASK_COMPLETE'
else
  echo 'TASK_FAILED'
  exit 1
fi
