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

for coll in $colls;
do
   echo "Creating now "$coll" master files"
   if [[ $mode == "scp" ]]; then
       scp $processing_user@$processing_server:/bases/org.000/iso/art.$coll/artigo.iso $processing_path/iso/$coll/artigo.iso
       scp $processing_user@$processing_server:/bases/org.000/iso/tit.$coll/title.iso $processing_path/iso/$coll/title.iso
       scp $processing_user@$processing_server:/bases/org.000/iso/b4c.$coll/bib4cit.iso $processing_path/iso/$coll/bib4cit.iso
   fi
   $cisis_dir/mx iso=$processing_path/iso/$coll/artigo.iso "proc='a992#$coll#'" append=$processing_path/databases/isis/artigo -all now
   $cisis_dir/mx iso=$processing_path/iso/$coll/title.iso "proc='a992#$coll#'" append=$processing_path/databases/isis/title -all now
   $cisis_dir/mx iso=$processing_path/iso/$coll/bib4cit.iso "proc='a992#$coll#'" append=$processing_path/databases/isis/bib4cit -all now
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

$cisis_dir/mx $processing_path/databases/isis/artigo "pft=if p(v880) then,v992,v880,fi,/" -all now > $processing_path/sh/legacy_identifiers.txt

cd sh
./loading_ids.py
cd ..

echo "Creating json files for each article"
mkdir -p $processing_path/output/isos/
total_pids=`wc -l $processing_path/sh/new_identifiers.txt`
from=1
for pid in `cat $processing_path/sh/new_identifiers.txt`;
do
    collection=${pid:0:3}
    pid=${pid:3:23}
    echo $from"/"$total_pids "-" $pid
    from=$(($from+1))

    loaded=`curl -s -X GET "http://"$scielo_data_url"/api/v1/article/exists?code=$pid&collection=$collection"`
    if [[ $loaded == "false" ]]; then
        mkdir -p $processing_path/output/isos/$pid
        issn=${pid:1:9}
        len=${#pid}
        if [[ $len -eq 23 ]]; then
            $cisis_dir/mx $processing_path/databases/isis/artigo  btell="0" $collection$pid count=1 iso=$processing_path/output/isos/$pid/$pid"_artigo.iso" -all now
            $cisis_dir/mx $processing_path/databases/isis/title   btell="0" $collection$issn count=1 iso=$processing_path/output/isos/$pid/$pid"_title.iso" -all now
            $cisis_dir/mx $processing_path/databases/isis/bib4cit btell="0" $collection$pid"$" count=1 iso=$processing_path/output/isos/$pid/$pid"_bib4cit.iso" -all now
            cd sh
            ./isis2json.py $processing_path/output/isos/$pid/$pid"_artigo.iso" -c -p v -t 3 > $processing_path/output/isos/$pid/$pid"_artigo.json"
            ./isis2json.py $processing_path/output/isos/$pid/$pid"_title.iso" -c -p v -t 3 > $processing_path/output/isos/$pid/$pid"_title.json"
            ./isis2json.py $processing_path/output/isos/$pid/$pid"_bib4cit.iso" -c -p v -t 3 > $processing_path/output/isos/$pid/$pid"_bib4cit.json"
            ./packing_json.py 'article' $pid > $processing_path/output/isos/$pid/$pid"_package.json"
            cd ..
            curl -H "Content-Type: application/json" --data @$processing_path/output/isos/$pid/$pid"_package.json" -X POST "http://"$scielo_data_url"/api/v1/article/add?admintoken="$admintoken
            rm -rf $processing_path/output/isos/$pid
        fi
    else
        echo "article alread processed!!!"
    fi
done

echo "Removing exceded files from Article Meta"

tot_to_remove=`cat $processing_path/sh/to_remove_identifiers.txt | wc -l`

if (($tot_to_remove < 1000)); then
    for pid in `cat $processing_path/sh/to_remove_identifiers.txt`;
    do
      collection=${pid:0:3}
      pid=${pid:3:23}
      durl="http://"$scielo_data_url"/api/v1/article/delete?code="$pid"&collection="$collection"&admintoken="$admintoken
      curl -X DELETE $durl
    done
else
  echo "To many files to remove. I will not remove then, please check it before"
fi

echo "Updating title database"

$cisis_dir/mx $processing_path/databases/isis/title "pft=v400,/" -all now > issns.txt

itens=`cat issns.txt`

for issn in $itens; do
   echo "Updating: "$issn 
   mkdir -p $processing_path/output/isos/$issn
   $cisis_dir/mx $processing_path/databases/isis/title btell="0" $issn iso=$processing_path/output/isos/$issn/$issn"_title.iso" -all now
   cd sh
   ./isis2json.py $processing_path/output/isos/$issn/$issn"_title.iso" -c -p v -t 3 > $processing_path/output/isos/$issn/$issn"_title.json"
   ./packing_json.py 'journal' $issn > $processing_path/output/isos/$issn/$issn"_package.json"
   cd ..
   curl -H "Content-Type: application/json" --data @$processing_path/output/isos/$issn/$issn"_package.json" -X POST "http://"$scielo_data_url"/api/v1/journal/add?admintoken="$admintoken
   rm -rf $processing_path/output/isos/$issn
done

rm issns.txt




