#!/bin/sh
# Compute sum of 1..20
sum=0
i=1
while [ $i -le 20 ]; do
  sum=$((sum + i))
  i=$((i + 1))
done
echo "sum(1..20) = $sum"
echo "expected = 210"
if [ "$sum" -eq 210 ]; then
  echo 'TASK_COMPLETE'
else
  echo 'TASK_FAILED'
  exit 1
fi
