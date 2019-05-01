// Make buttons in jQuery button style
$( function() {
  $( "button[type=button]" ).button();
  $( "input[type=submit]" ).button();
});

// set tabs
$(document).ready( function() {
  $( "#tabs" ).tabs();
  $( ".vrtTabs" ).tabs();
  $( ".vrtTabs" ).tabs().addClass( "ui-tabs-vertical ui-helper-clearfix" );
  $( ".vrtTabs li" ).removeClass( "ui-corner-top" ).addClass( "ui-corner-left" );
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