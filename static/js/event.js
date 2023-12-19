const amount_header_string = "Amount"

function rateOnChange(event) {
  toC = event.value
  rate = yenRate[toC]
  for (let strong of document.getElementsByName("switchableCurrency")) {
    strong.innerHTML = (parseFloat(strong.attributes['value'].value) * rate).toFixed(2);
  }
}

function table_search(input) {
  table = document.getElementById("last_100_records_table");
  filter = input.value.toLowerCase();
  tr = table.getElementsByTagName("tr");
  input_id = input.id.split("_")[0]

  const amount_th = document.getElementById("record_table_" + amount_header_string + "_header_th");
  const amount_th_textNode = amount_th.childNodes[0];
  
  let sub_amount = 0
  
  // Loop through all table rows, and hide those who don't match the search query
  for (i = 0; i < tr.length; i++) {
    td = tr[i].getElementsByClassName("searchable_" + input_id)[0];
    if (td && filter !== "") {
      txtValue = td.textContent || td.innerText;

      if (txtValue.toLowerCase().includes(filter)) {
        tr[i].style.display = "";
        let row_amount_str = tr[i].getElementsByClassName("searchable_" + amount_header_string)[0].innerText;
        sub_amount = sub_amount + parseFloat(row_amount_str);
      } else {
        tr[i].style.display = "none";
      }
    } else {
      // display if no filter 
      tr[i].style.display = "";
    }
  }

  // change header for filtered result only
  if (filter !== "")
  {
    amount_th_textNode.nodeValue = amount_header_string + " (" + sub_amount.toFixed(2) + ")";
  }
  else
  {
    amount_th_textNode.nodeValue = amount_header_string;
  }

}

function calculator_eval(calc_input)
{
  const amount_label = document.getElementById("new_amount_label");
  const amount_input = document.getElementById("new_amount_input");
  if (calc_input.value === "")
  {
    amount_label.innerText = amount_header_string
    return
  }

  try {
    const result = eval(calc_input.value); 
    amount_input.value = result;
    amount_label.innerText = amount_header_string + " (calc)"
  } catch (e) {
    amount_label.innerText = amount_header_string + " (calc err)"
    amount_input.value = 0
  }
}

function amount_input_edited()
{
  document.getElementById("calc_eval_input").value = "";
  document.getElementById("new_amount_label").innerText = amount_header_string;
}