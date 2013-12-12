total=250000
pace=10000
next=0
while [ $next -lt $total ];
do
   echo "from="$next" count="$pace
   nohup ./xmlwos_run.sh $next $pace &
   next=$(($next + $pace))
done

