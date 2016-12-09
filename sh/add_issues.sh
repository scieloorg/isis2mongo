# Path for the script root directory
BASEDIR=$(dirname $0)

echo "Script running with CISIS version:"
$BASEDIR/../cisis/mx what

mkdir -p $BASEDIR/../databases
mkdir -p $BASEDIR/../isos
mkdir -p $BASEDIR/../tmp
mkdir -p $BASEDIR/../output

echo "Listing legacy issues identifiers"
$BASEDIR/../cisis/mx $BASEDIR/../databases/issue "pft=if p(v880) then,v992,v880,v91, fi,/" -all now > $BASEDIR/legacy_issue_identifiers.txt

echo "listing articlemeta issues identifiers"
./loading_issue_ids.py

echo "Adding Issues"

echo "Creating json files for each new issue"
mkdir -p $BASEDIR/../output/isos/
total_pids=`wc -l $BASEDIR/new_issue_identifiers.txt`
from=1
for pid in `cat $BASEDIR/new_issue_identifiers.txt`;
do
    collection=${pid:0:3}
    pid=${pid:3:17}
    echo $from"/"$total_pids "-" $collection$pid
    from=$(($from+1))
    loaded=`curl -s -X GET "http://"$ARTICLEMETA_DOMAIN"/api/v1/issue/exists/?code=$pid&collection=$collection"`
    if [[ $loaded == "false" ]]; then
        mkdir -p $BASEDIR/../output/isos/$pid
        issn=${pid:0:9}
        len=${#pid}
        if [[ $len -eq 17 ]]; then
            $BASEDIR/../cisis/mx $BASEDIR/../databases//title   btell="0" $collection$issn count=1 iso=$BASEDIR/../output/isos/$pid/$pid"_title.iso" -all now
            $BASEDIR/../cisis/mx $BASEDIR/../databases//issue  btell="0" $collection$pid count=1 iso=$BASEDIR/../output/isos/$pid/$pid"_issue.iso" -all now
            ./isis2json.py $BASEDIR/../output/isos/$pid/$pid"_title.iso" -c -p v -t 3 > $BASEDIR/../output/isos/$pid/$pid"_title.json"
            ./isis2json.py $BASEDIR/../output/isos/$pid/$pid"_issue.iso" -c -p v -t 3 > $BASEDIR/../output/isos/$pid/$pid"_issue.json"
            ./packing_json.py 'issue' $pid > $BASEDIR/../output/isos/$pid/$pid"_package.json"
            curl -H "Content-Type: application/json" --data @$BASEDIR/../output/isos/$pid/$pid"_package.json" -X POST "http://"$ARTICLEMETA_DOMAIN"/api/v1/issue/add/?admintoken="$ARTICLEMETA_ADMINTOKEN
            rm -rf $BASEDIR/../output/isos/$pid
        fi
    else
        echo "issue alread processed!!!"
        echo $collection$pid >> $BASEDIR/update_issue_identifiers.txt
    fi
done
