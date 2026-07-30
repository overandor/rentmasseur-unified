#!/bin/sh
sum=0
i=1
while [ $i -le 10 ]; do
sum=$((sum + i))
i=$((i + 1))
done
echo "solve(10) = $sum"
if [ "$sum" -eq 55 ]; then
echo 'TEST PASSED'
else
echo 'TEST FAILED'
exit 1
fi
