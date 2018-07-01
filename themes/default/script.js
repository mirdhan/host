function isInArray(value, array) {
  return array.indexOf(value) > -1;
}

function sleep(time) {
  return new Promise((resolve) => setTimeout(resolve, time));
}

function updatePage(title, header, buttons) {
  document.title = title + " | PS4 Exploit Host by Al-Azif";
  document.getElementById("title").innerHTML = title;
  document.getElementById("header").innerHTML = header;
  document.getElementById("buttons").innerHTML = buttons;
}

function resetPage() {
  history.pushState("", document.title, window.location.pathname + window.location.search);
  updatePage("Firmware Selection", "Firmware", firmwares);
}

function getFirmwares() {
  var firmwareSpoofs = {
    "5.51": "4.55",
    "5.07": "5.05"
  };
  var ua = navigator.userAgent;
  var currentFirmware = ua.substring(ua.indexOf("5.0 (") + 19, ua.indexOf(") Apple"));
  if (firmwareSpoofs.hasOwnProperty(currentFirmware)) {
    currentFirmware = firmwareSpoofs[currentFirmware];
  }
  var firmwares = "";
  x = 0;
  if (data["firmwares"].length == 2 && data["firmwares"][0] != "No Exploits Found" && data["firmwares"][0] != "I/O Error on Host") {
    window.location.hash = data["firmwares"][0];
  }
  for (var i = 0, len = data["firmwares"].length; i < len; i++) {
    x += 1;
    if (currentFirmware == data["firmwares"][i]) {
      firmwares += "<a href=\"#" + data["firmwares"][i] + "\"><button class=\"btn btn-main\">" + data["firmwares"][i] + "</button></a>";
    } else if (data["firmwares"][i] == "[Cache All]") {
      if (navigator.onLine && data["firmwares"].length > 1) {
        firmwares += "<button class=\"btn btn-main\" onClick=\"document.getElementById('ifr').setAttribute('src', '/cache/all/index.html');\">[Cache All]</button>";
      }
    } else {
      firmwares += "<a href=\"#" + data["firmwares"][i] + "\"><button class=\"btn btn-disabled\">" + data["firmwares"][i] + "</button></a>";
    }
    if (x >= 3) {
      firmwares += "<br>";
      x = 0;
    }
  }
  return firmwares;
}

function getExploits() {
  var hash = window.location.hash.substr(1);
  var exploits = "";
  x = 0;
  for (var i = 0, len = data[hash].length; i < len; i++) {
    x += 1;
    if (data[hash][i] == "[Back]") {
      exploits += "<a id=\"back\" href=\"#back\"><button class=\"btn btn-main\">" + data[hash][i] + "</button></a>";
    } else if (data[hash][i] == "[Cache]") {
      if (navigator.onLine && data[hash].length > 2) {
        exploits += "<button class=\"btn btn-main\" onClick=\"document.getElementById('ifr').setAttribute('src', '/cache/" + hash + "/index.html');\">[Cache]</button>";
      }
    } else {
      exploits += "<button class=\"btn btn-main\" onClick=\"showLoader(); document.getElementById('ifr').setAttribute('src', '" + exploitBase + hash + "/" + data[hash][i] + "/index.html');\">" + data[hash][i] + "</button>";
    }
    if (x >= 3) {
      exploits += "<br>";
      x = 0;
    }
  }
  return exploits;
}

function firmwareSelected() {
  var hash = window.location.hash.substr(1);
  if (!isInArray(hash, firmwares)) {
    resetPage();
  } else {
    updatePage("Exploit Selection", hash, getExploits());
  }
}

function clearFrame() {
  document.getElementById("ifr").setAttribute("src", "");
}

function ondownloading() {
  document.getElementById("cacheOverlay").style.display = "block";
}

function onprogress(percent) {
  document.getElementById("barLoad").style.width = percent + '%';
  document.getElementById("barLoad").innerHTML = percent + '%';
}

function oncached() {
  clearFrame();
  document.getElementById("cacheOverlay").style.display = "none";
  alert('Application cached successfully!')
}

function onupdateready() {
  clearFrame();
  document.getElementById("cacheOverlay").style.display = "none";
  var r = confirm("Cache updated! Press Ok to reload the page.");
  if (r == true) {
    window.location.reload(true);
  }
}

function onnoupdate() {
  clearFrame();
  document.getElementById("cacheOverlay").style.display = "none";
  alert("No update available");
}

function onerror() {
  clearFrame();
  document.getElementById("cacheOverlay").style.display = "none";
  alert("Error caching resources!")
}

function onobsolete() {
  clearFrame();
  document.getElementById("cacheOverlay").style.display = "none";
  alert("Manifest returned a 404, cache was deleted");
}

function showLoader() {
  document.getElementById("exploitMessage").innerHTML = "";
  document.getElementById("exploitOverlay").style.display = "block";
  document.getElementById("loader").style.display = "block";
}

function hideLoader(message, wait) {
  document.getElementById("loader").style.display = "none";
  document.getElementById("exploitMessage").innerHTML = message;
  sleep(wait).then(() => {
    document.getElementById("exploitOverlay").style.display = "none";
  });
}

/*
Copyright (c) 2017-2018 Al Azif, https://github.com/Al-Azif/ps4-exploit-host

Permission is hereby granted, free of charge, to any person obtaining
a copy of this software and associated documentation files (the
"Software"), to deal in the Software without restriction, including
without limitation the rights to use, copy, modify, merge, publish,
distribute, sublicense, and/or sell copies of the Software, and to
permit persons to whom the Software is furnished to do so, subject to
the following conditions:

The above copyright notice and this permission notice shall be
included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
*/
