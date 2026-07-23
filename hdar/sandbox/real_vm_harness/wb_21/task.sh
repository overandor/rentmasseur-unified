#!/bin/sh
# Compute sum of 1..6
sum=0
i=1
while [ $i -le 6 ]; do
  sum=$((sum + i))
  i=$((i + 1))
done
echo "sum(1..6) = $sum"
echo "expected = 21"
if [ "$sum" -eq 21 ]; then
  echo 'TASK_COMPLETE'
else
  echo 'TASK_FAILED'
  exit 1
fi
