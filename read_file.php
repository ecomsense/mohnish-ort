<?php
// read_file.php
//

$filename = '/var/www/clients/client4/web11/home/sai_2414/no_env/vwap-options/data/log.txt';

if (file_exists($filename)) {
	$lines = file($filename, FILE_SKIP_EMPTY_LINES);
	$last_lines = array_slice($lines, -30);
	$reversed = array_reverse($last_lines);
	foreach ($reversed as $line) {
		echo nl2br(htmlspecialchars($line)) . "\n";
	}
} else {
	echo $filename . "not found";
}
