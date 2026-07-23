#!/bin/sh
# Compute sum of 1..19
sum=0
i=1
while [ $i -le 19 ]; do
  sum=$((sum + i))
  i=$((i + 1))
done
echo "sum(1..19) = $sum"
echo "expected = 190"
if [ "$sum" -eq 190 ]; then
  echo 'TASK_COMPLETE'
else
  echo 'TASK_FAILED'
  exit 1
fi
