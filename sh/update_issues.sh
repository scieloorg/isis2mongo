# Path for the script root directory
BASEDIR=$(dirname $0)

echo "Script running with CISIS version:"
$BASEDIR/../cisis/mx what

mkdir -p $BASEDIR/../databases
mkdir -p $BASEDIR/../isos
mkdir -p $BASEDIR/../tmp
mkdir -p $BASEDIR/../output

echo "Updating Issues"

mkdir -p $BASEDIR/../output/isos/
total_pids=`wc -l $BASEDIR/update_issue_identifiers.txt`
from=1
for pid in `cat $BASEDIR/update_issue_identifiers.txt`;
do
    collection=${pid:0:3}
    pid=${pid:3:17}
    echo $from"/"$total_pids "-" $collection$pid
    from=$(($from+1))
    mkdir -p $BASEDIR/../output/isos/$pid
    issn=${pid:0:9}
    len=${#pid}
    if [[ $len -eq 17 ]]; then
        $cisis_dir/mx $BASEDIR/../databases/title   btell="0" $collection$issn count=1 iso=$BASEDIR/../output/isos/$pid/$pid"_title.iso" -all now
        $cisis_dir/mx $BASEDIR/../databases/issue  btell="0" $collection$pid count=1 iso=$BASEDIR/../output/isos/$pid/$pid"_issue.iso" -all now
        ./isis2json.py $BASEDIR/../output/isos/$pid/$pid"_title.iso" -c -p v -t 3 > $BASEDIR/../output/isos/$pid/$pid"_title.json"
        ./isis2json.py $BASEDIR/../output/isos/$pid/$pid"_issue.iso" -c -p v -t 3 > $BASEDIR/../output/isos/$pid/$pid"_issue.json"
        ./packing_json.py 'issue' $pid > $BASEDIR/../output/isos/$pid/$pid"_package.json"
        curl -H "Content-Type: application/json" --data @$BASEDIR/../output/isos/$pid/$pid"_package.json" -X POST "http://"$ARTICLEMETA_DOMAIN"/api/v1/issue/update/?admintoken="$ARTICLEMETA_ADMINTOKEN
        rm -rf $BASEDIR/../output/isos/$pid
    fi
done

echo '' > $BASEDIR/update_issue_identifiers.txt
