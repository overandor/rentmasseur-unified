#!/bin/sh
# Compute sum of 1..47
sum=0
i=1
while [ $i -le 47 ]; do
  sum=$((sum + i))
  i=$((i + 1))
done
echo "sum(1..47) = $sum"
echo "expected = 1128"
if [ "$sum" -eq 1128 ]; then
  echo 'TASK_COMPLETE'
else
  echo 'TASK_FAILED'
  exit 1
fi
