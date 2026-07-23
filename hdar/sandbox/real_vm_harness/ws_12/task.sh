#!/bin/sh
# Compute sum of 1..2
sum=0
i=1
while [ $i -le 2 ]; do
  sum=$((sum + i))
  i=$((i + 1))
done
echo "sum(1..2) = $sum"
echo "expected = 3"
if [ "$sum" -eq 3 ]; then
  echo 'TASK_COMPLETE'
else
  echo 'TASK_FAILED'
  exit 1
fi
