#!/bin/sh
# Compute sum of 1..79
sum=0
i=1
while [ $i -le 79 ]; do
  sum=$((sum + i))
  i=$((i + 1))
done
echo "sum(1..79) = $sum"
echo "expected = 3160"
if [ "$sum" -eq 3160 ]; then
  echo 'TASK_COMPLETE'
else
  echo 'TASK_FAILED'
  exit 1
fi
