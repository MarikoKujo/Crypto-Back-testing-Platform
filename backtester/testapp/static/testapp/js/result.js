// Make buttons in jQuery button style
$( function() {
  $( "button[type=button]" ).button();
  $( "input[type=submit]" ).button();
});

// start new backtests
$( function() {
  dialog = $( "#dialog-confirm" ).dialog({
    autoOpen: false,
    resizable: false,
    height: "auto",
    width: 400,
    modal: true,
    buttons: {
      "OK": function() {
        $( this ).dialog( "close" );
        // go back to index
        document.location.href = $("#dialog-confirm").attr("data-url");
      },
      Cancel: function() {
        $( this ).dialog( "close" );
      }
    }
  });

  $( "#startnew" ).button().on( "click", function() {
  	dialog.dialog( "open" );
  });
});

// export to file
// Deprecated: now directly return a file
// $( function() {
//   var frm = $( ".expform" );
//   var startnew = $( "#startnew" );
//   var expbutton = $(".expbutton");
//   frm.submit( function( event ) {
//     event.preventDefault();
//     // disable buttons
//     startnew.button("option", "disabled", true);
//     expbutton.prop("disabled", "true");
    
//     // get current active backtest result tab according to form name
//     filetab = $(this).attr("name");
//     var infolab;
//     // get corresponding info label
//     switch(filetab) {
//       case "expfile-2":
//         infolab = $("#expinfo-2");
//         break;
//       case "expfile-3":
//         infolab = $("#expinfo-3");
//         break;
//       default:
//         infolab = $("#expinfo-1");
//     }
//     infolab.attr("style", "color:black;");
//     infolab.html("Processing...");
//     // get the destination view url
//     url = $(this).attr("action");
//     // get form data
//     data = $(this).serialize();
//     $.post(url, data, function(data) {
//       // set info label text color
//       if (data.indexOf("Error") !== -1) {  // "Error" in response
//         infolab.attr("style", "color:red;");
//       } else {
//         infolab.attr("style", "color:green;");
//       }
//       // set info label content
//       infolab.html(data);
//       // enable buttons
//       startnew.button("option", "disabled", false);
//       expbutton.removeAttr('disabled');
//     });
//   });
// });