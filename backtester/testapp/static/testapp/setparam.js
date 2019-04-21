// jQuery datepickers, select a date range
$(document).ready(function() {
    var dateFormat = "yy-mm-dd",
      from = $( "#from" ).datepicker({
        changeMonth: true,
	      changeYear: true,
	      minDate: new Date("2018-10-24"),
	      maxDate: "-2D",
	      dateFormat: "yy-mm-dd"
        })
        .on( "change", function() {
          to.datepicker( "option", "minDate", getDate( this ) );
        }),
      to = $( "#to" ).datepicker({
        changeMonth: true,
        changeYear: true,
        minDate: new Date("2018-10-25"),
        maxDate: "-1D",
        dateFormat: "yy-mm-dd"
      })
      .on( "change", function() {
        from.datepicker( "option", "maxDate", getDate( this ) );
      });
 
    function getDate( element ) {
      var date;
      try {
        date = $.datepicker.parseDate( dateFormat, element.value );
      } catch( error ) {
        date = null;
      }
 
      return date;
    }
});

// Restrict number of strategy files to 1-3
$(function() {
  var // Define maximum number of files.
      max_file_number = 3,
      // Define your form id or class or just tag.
      $form = $('#backtestparams'), 
      // Define your upload field class or id or tag.
      $file_upload = $('#strategies', $form), 
      // Define your submit class or id or tag.
      $button = $('#submitparams', $form); 

  // Disable submit button on page ready.
  $button.prop('disabled', true);

  $file_upload.on('change', function () {
    var number_of_images = $(this)[0].files.length;
    if (number_of_images > max_file_number) {
      alert(`You can upload maximum ${max_file_number} files.`);
      $(this).val('');
      $("#submitparams").button("option", "disabled", true);
    } else {
      $("#submitparams").button("option", "disabled", false);
    }
  });
});

// jQuery dialog, settings button
$( function() {
  var dialog, form,

    numberRegex = /^[0-9]*[.,]?[0-9]+$/,
    amount = $( "#commission" ),
    allFields = $( [] ).add( amount ),
    tips = $( ".validateTips" );

  function updateTips( t ) {
    tips
      .text( t )
      .addClass( "ui-state-highlight" );
    setTimeout(function() {
      tips.removeClass( "ui-state-highlight", 1500 );
    }, 500 );
  }

  function checkRegexp( o, regexp, n ) {
    if ( !( regexp.test( o.val() ) ) ) {
      o.addClass( "ui-state-error" );
      updateTips( n );
      return false;
    } else {
      return true;
    }
  }

  function addUser() {
    var valid = true;
    allFields.removeClass( "ui-state-error" );

    valid = valid && checkRegexp( amount, numberRegex, "Please enter a non-negative number with or without decimals" );
    
    if ( valid ) {
      $("#commamount").val(amount.val());
      var costMethod = $('input[name=costmethod]:checked').val();
      $("#comm").val(costMethod);
      dialog.dialog( "close" );
    }
    return valid;
  }

  dialog = $( "#dialog-form" ).dialog({
    autoOpen: false,
    height: 400,
    width: 350,
    modal: true,
    buttons: {
      "OK": addUser,
      Cancel: function() {
        dialog.dialog( "close" );
      }
    },
    close: function() {
      form[ 0 ].reset();
      allFields.removeClass( "ui-state-error" );
    }
  });

  form = dialog.find( "form" ).on( "submit", function( event ) {
    event.preventDefault();
    addUser();
  });

  $( "#pertrade" ).on( "click", function() {
    $( "#percentmark" ).attr("style", "display:none;");
  });

  $( "#pershare" ).on( "click", function() {
    $( "#percentmark" ).attr("style", "");
  });

  $( "#settings" ).button().on( "click", function() {
    dialog.dialog( "open" );
    if ( $("#commamount").val() ) {
      // set commission to value after last modification
      $("#commission").val( $("#commamount").val() );
    }
    var costMethod = $("#comm").val();
    if (costMethod) {
      if (costMethod == "pershare") {
        $("#pershare").prop("checked", "checked");
      } else {
        $("#pertrade").prop("checked", "checked");
      }
    }
  });
} );

// Make input file and submit buttons in jQuery button style
$( function() {
  $( "input[type=submit], input[type=file]" ).button();
});

// Dates should be non-empty. Starting cash should > 0.
$( function() {
  $( "#submitparams" ).on("click", function() {
    if ( $("#from").val() == "" || $("#to").val() == "") {
      event.preventDefault();
      alert("Please set both dates.");
    } else if (parseFloat( $("#capital").val() ) <= 0) {
      event.preventDefault();
      alert("Capital base should be greater than zero.");
    }
  });
});



function msg() {
  alert("It works.");
}

