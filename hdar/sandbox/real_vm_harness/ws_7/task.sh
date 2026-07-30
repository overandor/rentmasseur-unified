#!/bin/sh
# Compute sum of 1..80
sum=0
i=1
while [ $i -le 80 ]; do
  sum=$((sum + i))
  i=$((i + 1))
done
echo "sum(1..80) = $sum"
echo "expected = 3240"
if [ "$sum" -eq 3240 ]; then
  echo 'TASK_COMPLETE'
else
  echo 'TASK_FAILED'
  exit 1
fi
