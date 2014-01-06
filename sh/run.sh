processing_path="/bases/isis2mongo"

. $processing_path/sh/config.sh

echo "Script running with CISIS version:"
$cisis_dir/mx what

mkdir -p $processing_path/databases
mkdir -p $processing_path/iso
mkdir -p $processing_path/tmp
mkdir -p $processing_path/output

colls=`ls -1 $processing_path/iso`
rm -f $processing_path/databases/isis/artigo.*
rm -f $processing_path/databases/isis/title.*
rm -f $processing_path/databases/isis/bib4cit.*

for coll in $colls;
do
    echo "Creating now "$coll" master files"
    if [[ $mode == "scp" ]]; then
        scp $processing_user@$processing_server:/bases/org.000/iso/art.$coll/artigo.iso $processing_path/iso/$coll/artigo.iso
        scp $processing_user@$processing_server:/bases/org.000/iso/tit.$coll/title.iso $processing_path/iso/$coll/title.iso
        scp $processing_user@$processing_server:/bases/org.000/iso/b4c.$coll/bib4cit.iso $processing_path/iso/$coll/bib4cit.iso
    fi
    $cisis_dir/mx iso=$processing_path/iso/$coll/artigo.iso append=$processing_path/databases/isis/artigo -all now
    $cisis_dir/mx iso=$processing_path/iso/$coll/title.iso append=$processing_path/databases/isis/title -all now
    $cisis_dir/mx iso=$processing_path/iso/$coll/bib4cit.iso append=$processing_path/databases/isis/bib4cit -all now
    if [[ $mode == "scp" ]]; then
        rm $processing_path/iso/$coll/artigo.iso
        rm $processing_path/iso/$coll/title.iso
        rm $processing_path/iso/$coll/bib4cit.iso
    fi
done

echo "Indexing databases according to FSTs"
$cisis_dir/mx $processing_path/databases/isis/artigo  fst="@$processing_path/fst/artigo.fst"  fullinv/ansi=$processing_path/databases/isis/artigo  tell=1000  -all now
$cisis_dir/mx $processing_path/databases/isis/title   fst="@$processing_path/fst/title.fst"   fullinv/ansi=$processing_path/databases/isis/title   tell=10    -all now
$cisis_dir/mx $processing_path/databases/isis/bib4cit fst="@$processing_path/fst/bib4cit.fst" fullinv/ansi=$processing_path/databases/isis/bib4cit tell=10000 -all now

echo "Creating articles processing list"
from=$1
count=$2
range=""

if [[ $from != "" ]]; then
    range="from="$from
fi

if [[ $count != "" ]]; then
    range=$range" count="$count
fi

articles_processing_list="aplf"$from"c"$count".txt"
$cisis_dir/mx $processing_path/databases/isis/artigo "pft=if p(v880) then,v880,fi,/" $range -all now > $processing_path/tmp/$articles_processing_list

echo "Creating json files for each article"
mkdir -p $processing_path/output/isos/
total_pids=`wc -l $processing_path/tmp/$articles_processing_list`
from=1
for pid in `cat $processing_path/tmp/$articles_processing_list`;
do
    echo $from"/"$total_pids "-" $pid
    from=$(($from+1))

    loaded=`curl -s -X GET "http://"$scielo_data_url"/api/v1/is_loaded?code="$pid`
    if [[ $loaded == "False" ]]; then
        mkdir -p $processing_path/output/isos/$pid
        issn=${pid:1:9}
        len=${#pid}
        if [[ $len -eq 23 ]]; then
            $cisis_dir/mx $processing_path/databases/isis/artigo  btell="0" pid=$pid   iso=$processing_path/output/isos/$pid/$pid"_artigo.iso" -all now
            $cisis_dir/mx $processing_path/databases/isis/title   btell="0" $issn      iso=$processing_path/output/isos/$pid/$pid"_title.iso" -all now
            $cisis_dir/mx $processing_path/databases/isis/bib4cit btell="0" $pid"$"    iso=$processing_path/output/isos/$pid/$pid"_bib4cit.iso" -all now

            python isis2json.py $processing_path/output/isos/$pid/$pid"_artigo.iso" -c -p v -t 3 > $processing_path/output/isos/$pid/$pid"_artigo.json"
            python isis2json.py $processing_path/output/isos/$pid/$pid"_title.iso" -c -p v -t 3 > $processing_path/output/isos/$pid/$pid"_title.json"
            python isis2json.py $processing_path/output/isos/$pid/$pid"_bib4cit.iso" -c -p v -t 3 > $processing_path/output/isos/$pid/$pid"_bib4cit.json"
            curl -X POST "http://"$scielo_data_url"/api/v1/article?code="$pid
            rm -rf $processing_path/output/isos/$pid
        fi
    else
        echo "article alread processed!!!"
    fi
done