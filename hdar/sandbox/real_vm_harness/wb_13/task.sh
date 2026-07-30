#!/bin/sh
# Compute sum of 1..56
sum=0
i=1
while [ $i -le 56 ]; do
  sum=$((sum + i))
  i=$((i + 1))
done
echo "sum(1..56) = $sum"
echo "expected = 1596"
if [ "$sum" -eq 1596 ]; then
  echo 'TASK_COMPLETE'
else
  echo 'TASK_FAILED'
  exit 1
fi
