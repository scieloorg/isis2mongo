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

echo "RUNNING ADD ARTICLES"
$processing_path/sh/add_articles.sh > $processing_path/log/add_articles.log

echo "RUNNING DELETION"
$processing_path/sh/delete.sh > $processing_path/log/delete.log

echo "RUNNING UPDATE ARTICLES"
$processing_path/sh/update_articles.sh > $processing_path/log/update_articles.log

echo "RUNNING UPDATE TITLES"
$processing_path/sh/update_titles.sh > $processing_path/log/update_titles.log
