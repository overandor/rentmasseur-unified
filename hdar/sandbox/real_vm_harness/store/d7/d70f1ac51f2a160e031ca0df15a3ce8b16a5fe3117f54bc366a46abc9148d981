#!/bin/sh
# Compute sum of 1..91
sum=0
i=1
while [ $i -le 91 ]; do
  sum=$((sum + i))
  i=$((i + 1))
done
echo "sum(1..91) = $sum"
echo "expected = 4186"
if [ "$sum" -eq 4186 ]; then
  echo 'TASK_COMPLETE'
else
  echo 'TASK_FAILED'
  exit 1
fi
