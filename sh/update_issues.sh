processing_path="/bases/isis2mongo"

cd $processing_path

. $processing_path/sh/config.sh

echo "Script running with CISIS version:"
$cisis_dir/mx what

mkdir -p $processing_path/databases
mkdir -p $processing_path/iso
mkdir -p $processing_path/tmp
mkdir -p $processing_path/output

echo "Updating Issues"

mkdir -p $processing_path/output/isos/
total_pids=`wc -l $processing_path/sh/update_issue_identifiers.txt`
from=1
for pid in `cat $processing_path/sh/update_issue_identifiers.txt`;
do
    collection=${pid:0:3}
    pid=${pid:3:17}
    echo $from"/"$total_pids "-" $collection$pid
    from=$(($from+1))
    mkdir -p $processing_path/output/isos/$pid
    issn=${pid:0:9}
    len=${#pid}
    if [[ $len -eq 17 ]]; then
        $cisis_dir/mx $processing_path/databases/isis/title   btell="0" $collection$issn count=1 iso=$processing_path/output/isos/$pid/$pid"_title.iso" -all now
        $cisis_dir/mx $processing_path/databases/isis/issue  btell="0" $collection$pid count=1 iso=$processing_path/output/isos/$pid/$pid"_issue.iso" -all now
        cd sh
        ./isis2json.py $processing_path/output/isos/$pid/$pid"_title.iso" -c -p v -t 3 > $processing_path/output/isos/$pid/$pid"_title.json"
        ./isis2json.py $processing_path/output/isos/$pid/$pid"_issue.iso" -c -p v -t 3 > $processing_path/output/isos/$pid/$pid"_issue.json"
        ./packing_json.py 'issue' $pid > $processing_path/output/isos/$pid/$pid"_package.json"
        cd ..
        curl -H "Content-Type: application/json" --data @$processing_path/output/isos/$pid/$pid"_package.json" -X POST "http://"$scielo_data_url"/api/v1/issue/update/?admintoken="$admintoken
        rm -rf $processing_path/output/isos/$pid
    fi
done

echo '' > $processing_path/sh/update_issue_identifiers.txt
