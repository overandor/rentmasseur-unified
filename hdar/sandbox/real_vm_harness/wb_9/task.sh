#!/bin/sh
# Compute sum of 1..48
sum=0
i=1
while [ $i -le 48 ]; do
  sum=$((sum + i))
  i=$((i + 1))
done
echo "sum(1..48) = $sum"
echo "expected = 1176"
if [ "$sum" -eq 1176 ]; then
  echo 'TASK_COMPLETE'
else
  echo 'TASK_FAILED'
  exit 1
fi
