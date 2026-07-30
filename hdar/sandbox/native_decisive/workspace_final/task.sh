#!/bin/sh
sum=0
i=1
while [ $i -le 100 ]; do
sum=$((sum + i))
i=$((i + 1))
done
echo "solve(100) = $sum"
echo 'TASK_COMPLETE'
