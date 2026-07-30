#!/bin/sh
# Compute sum of 1..10
sum=0
i=1
while [ $i -le 10 ]; do
  sum=$((sum + i))
  i=$((i + 1))
done
echo "sum(1..10) = $sum"
echo "expected = 55"
if [ "$sum" -eq 55 ]; then
  echo 'TASK_COMPLETE'
else
  echo 'TASK_FAILED'
  exit 1
fi
