# Path for the script root directory
processing_path="/bases/isis2mongo"

cd $processing_path

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
rm -f $processing_path/databases/isis/issue.*

for coll in $colls;
do
   echo "Creating now "$coll" master files"
   $cisis_dir/mx iso=$processing_path/iso/$coll/artigo.iso "proc='a992#$coll#'" append=$processing_path/databases/isis/artigo -all now
   $cisis_dir/mx iso=$processing_path/iso/$coll/title.iso "proc='a992#$coll#'" append=$processing_path/databases/isis/title -all now
   $cisis_dir/mx iso=$processing_path/iso/$coll/bib4cit.iso "proc='a992#$coll#'" append=$processing_path/databases/isis/bib4cit -all now
   $cisis_dir/mx iso=$processing_path/iso/$coll/issue.iso "proc='a992#$coll#'" append=$processing_path/databases/isis/issue -all now
done

echo "Creating Section CSV"
$cisis_dir/mx $processing_path/databases/isis/issue "pft=if p(v49) then (v992[1],'|',v35[1],v65[1]*0.4,s(f(val(s(v36[1]*4.3))+10000,2,0))*1.4,'|',v49^l,'|',v49^c,'|',v49^t,/) fi" -all now > $processing_path/output/section_codes.csv

echo "Indexing databases according to FSTs"
$cisis_dir/mx $processing_path/databases/isis/artigo  fst="@$processing_path/fst/artigo.fst"  fullinv/ansi=$processing_path/databases/isis/artigo  tell=1000  -all now
$cisis_dir/mx $processing_path/databases/isis/title   fst="@$processing_path/fst/title.fst"   fullinv/ansi=$processing_path/databases/isis/title   tell=10    -all now
$cisis_dir/mx $processing_path/databases/isis/bib4cit fst="@$processing_path/fst/bib4cit.fst" fullinv/ansi=$processing_path/databases/isis/bib4cit tell=10000 -all now

echo "Listing legacy identifiers"
$cisis_dir/mx $processing_path/databases/isis/artigo "pft=if p(v880) then,v992,v880,v91, fi,/" -all now > $processing_path/sh/legacy_identifiers.txt

echo "listing articlemeta identifiers"
cd sh
./loading_ids.py
cd ..

echo "Creating json files for each new article"
mkdir -p $processing_path/output/isos/
total_pids=`wc -l $processing_path/sh/new_identifiers.txt`
from=1
for pid in `cat $processing_path/sh/new_identifiers.txt`;
do
    collection=${pid:0:3}
    pid=${pid:3:23}
    echo $from"/"$total_pids "-" $pid
    from=$(($from+1))

    loaded=`curl -s -X GET "http://"$scielo_data_url"/api/v1/article/exists/?code=$pid&collection=$collection"`
    if [[ $loaded == "false" ]]; then
        mkdir -p $processing_path/output/isos/$pid
        issn=${pid:1:9}
        len=${#pid}
        if [[ $len -eq 23 ]]; then
            $cisis_dir/mx $processing_path/databases/isis/artigo  btell="0" $collection$pid count=1 iso=$processing_path/output/isos/$pid/$pid"_artigo.iso" -all now
            $cisis_dir/mx $processing_path/databases/isis/title   btell="0" $collection$issn count=1 iso=$processing_path/output/isos/$pid/$pid"_title.iso" -all now
            $cisis_dir/mx $processing_path/databases/isis/bib4cit btell="0" $collection$pid"$" iso=$processing_path/output/isos/$pid/$pid"_bib4cit.iso" -all now
            cd sh
            ./isis2json.py $processing_path/output/isos/$pid/$pid"_artigo.iso" -c -p v -t 3 > $processing_path/output/isos/$pid/$pid"_artigo.json"
            ./isis2json.py $processing_path/output/isos/$pid/$pid"_title.iso" -c -p v -t 3 > $processing_path/output/isos/$pid/$pid"_title.json"
            ./isis2json.py $processing_path/output/isos/$pid/$pid"_bib4cit.iso" -c -p v -t 3 > $processing_path/output/isos/$pid/$pid"_bib4cit.json"
            ./packing_json.py 'article' $pid > $processing_path/output/isos/$pid/$pid"_package.json"
            cd ..
            curl -H "Content-Type: application/json" --data @$processing_path/output/isos/$pid/$pid"_package.json" -X POST "http://"$scielo_data_url"/api/v1/article/add/?admintoken="$admintoken
            rm -rf $processing_path/output/isos/$pid
        fi
    else
        echo "article alread processed!!!"
        $collection$pid >> $processing_path/sh/update_identifiers.txt
    fi
done

# RUNNING DELETION
./delete.sh > ../log/delete.log

# RUNNING UPDATE ATICLES
./update_articles.sh > ../log/update_articles.log

# RUNNING UPDATE TITLES
./update_titles.sh > ../log/update_titles.log
