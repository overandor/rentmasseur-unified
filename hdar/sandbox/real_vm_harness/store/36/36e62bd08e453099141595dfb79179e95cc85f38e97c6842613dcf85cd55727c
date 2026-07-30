#!/bin/sh
# Compute sum of 1..61
sum=0
i=1
while [ $i -le 61 ]; do
  sum=$((sum + i))
  i=$((i + 1))
done
echo "sum(1..61) = $sum"
echo "expected = 1891"
if [ "$sum" -eq 1891 ]; then
  echo 'TASK_COMPLETE'
else
  echo 'TASK_FAILED'
  exit 1
fi
