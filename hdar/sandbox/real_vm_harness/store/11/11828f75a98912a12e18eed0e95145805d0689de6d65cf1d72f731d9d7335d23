#!/bin/sh
# Compute sum of 1..98
sum=0
i=1
while [ $i -le 98 ]; do
  sum=$((sum + i))
  i=$((i + 1))
done
echo "sum(1..98) = $sum"
echo "expected = 4851"
if [ "$sum" -eq 4851 ]; then
  echo 'TASK_COMPLETE'
else
  echo 'TASK_FAILED'
  exit 1
fi
