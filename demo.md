This is a demo page for the MoodleMD project, which you can find here:

[https://github.com/ST12901/MoodleMD](https://github.com/ST12901/MoodleMD)

The three panels below offer three different views of the example file included with the project. The first panel is in Markdown, the second is the .md file redendered as HTML, then the last panel shows the Moodle quiz questions generated from the example.

<div style="position:relative;">
<iframe style="width:33%; height:720px;left:0%;position:relative" src="./Example/example.md.txt" id="file1">
</iframe>
<iframe style="width:33%; height:720px;left:33%;position:absolute" src="./Example/example.html" id="file2">
</iframe>
<iframe style="width:33%; height:720px;left:66%;position:absolute" src="./Example/Example.html" id="file3">
</iframe>
</div>
<script>
var file1 = document.getElementById('file1');
var file2 = document.getElementById('file2');
var file3 = document.getElementById('file3');
var offset=0;
var offset2=0;

file1.onload = function() {
  file1.contentWindow.onscroll = function() {
    file2.contentWindow.scrollTo(0, Math.round(file1.contentWindow.pageYOffset+offset));
    file3.contentWindow.scrollTo(0, Math.round(file1.contentWindow.pageYOffset+offset2));
  };
};

file2.onload = function() {
  file2.contentWindow.onscroll = function() {
    offset=file2.contentWindow.pageYOffset-file1.contentWindow.pageYOffset;
  };
};
file3.onload = function() {
  file3.contentWindow.onscroll = function() {
    offset2=file3.contentWindow.pageYOffset-file1.contentWindow.pageYOffset;
  };
};
</script>
