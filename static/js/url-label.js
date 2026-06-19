(function (global) {
  function shortLabel(url) {
    if (!url) return "";
    const m = url.match(/\/useful_info_ec\/(\d+)\/?/);
    return m ? "/" + m[1] : url;
  }
  global.shortLabel = shortLabel;
})(window);
