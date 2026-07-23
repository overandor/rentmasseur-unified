#!/bin/sh
# Compute sum of 1..40
sum=0
i=1
while [ $i -le 40 ]; do
  sum=$((sum + i))
  i=$((i + 1))
done
echo "sum(1..40) = $sum"
echo "expected = 820"
if [ "$sum" -eq 820 ]; then
  echo 'TASK_COMPLETE'
else
  echo 'TASK_FAILED'
  exit 1
fi
