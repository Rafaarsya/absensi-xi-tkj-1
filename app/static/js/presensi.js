/* Form presensi siswa: keterangan untuk Izin/Sakit, dan izin lokasi hanya diminta saat benar-benar perlu
   (status Hadir dan verifikasi lokasi aktif). Nilai GPS dari klien hanya masukan; server yang memutuskan. */
(function () {
  "use strict";
  var form = document.getElementById("presensi-form");
  if (!form) return;
  var needGeo = form.getAttribute("data-geo") === "1";
  var noteWrap = document.getElementById("note-field");
  var note = document.getElementById("f-note");
  var geoHint = document.getElementById("geo-hint");
  var msg = document.getElementById("geo-msg");
  var submit = document.getElementById("submit-btn");
  var latEl = form.elements.lat, lngEl = form.elements.lng;

  function selected() {
    var r = form.querySelector('input[name="status"]:checked');
    return r ? r.value : "";
  }
  function sync() {
    var s = selected();
    var needNote = s === "I" || s === "S";
    noteWrap.hidden = !needNote;
    note.required = needNote;
    if (geoHint) geoHint.hidden = !(s === "H");
  }
  form.addEventListener("change", sync);
  sync();

  var busy = false;
  form.addEventListener("submit", function (e) {
    if (busy) { e.preventDefault(); return; }
    if (!(needGeo && selected() === "H")) return;
    if (latEl.value && lngEl.value) return;
    e.preventDefault();
    if (!navigator.geolocation) {
      msg.textContent = "Browser ini tidak mendukung lokasi. Gunakan browser lain atau hubungi wali kelas.";
      return;
    }
    busy = true;
    submit.disabled = true;
    msg.textContent = "Memeriksa lokasi perangkat…";
    navigator.geolocation.getCurrentPosition(function (pos) {
      latEl.value = pos.coords.latitude;
      lngEl.value = pos.coords.longitude;
      form.submit();
    }, function (err) {
      busy = false;
      submit.disabled = false;
      msg.textContent = err && err.code === 1
        ? "Izin lokasi ditolak. Ketuk ikon gembok di bilah alamat, ubah izin Lokasi menjadi Izinkan, lalu coba lagi."
        : "Lokasi belum bisa dibaca. Pastikan GPS aktif dan coba lagi.";
    }, { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 });
  });
})();
