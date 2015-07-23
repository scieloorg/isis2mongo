processing_path="/bases/isis2mongo"

cd $processing_path

. $processing_path/sh/config.sh

echo "Script running with CISIS version:"
$cisis_dir/mx what

mkdir -p $processing_path/databases
mkdir -p $processing_path/iso
mkdir -p $processing_path/tmp
mkdir -p $processing_path/output

echo "Updating title database"

$cisis_dir/mx $processing_path/databases/isis/title "pft=v992,v400,/" -all now > issns.txt

itens=`cat issns.txt`

for issn in $itens; do
   echo "Updating: "$issn
   collection=${issn:0:3}
   issn=${issn:3:9}
   mkdir -p $processing_path/output/isos/$issn
   $cisis_dir/mx $processing_path/databases/isis/title btell="0" $collection$issn iso=$processing_path/output/isos/$issn/$issn"_title.iso" -all now
   cd sh
   ./isis2json.py $processing_path/output/isos/$issn/$issn"_title.iso" -c -p v -t 3 > $processing_path/output/isos/$issn/$issn"_title.json"
   ./packing_json.py 'journal' $issn > $processing_path/output/isos/$issn/$issn"_package.json"
   cd ..
   curl -H "Content-Type: application/json" --data @$processing_path/output/isos/$issn/$issn"_package.json" -X POST "http://"$scielo_data_url"/api/v1/journal/add/?admintoken="$admintoken
   rm -rf $processing_path/output/isos/$issn
done

rm issns.txt
