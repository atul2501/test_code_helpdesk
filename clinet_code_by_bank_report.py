frappe.query_reports["Bank Reports2"] = {
    onload: function(report) {
        report.page.add_inner_button("Export TXT", function() {

            let data = report.data || [];

            if (!data.length) {
                frappe.msgprint("No data found");
                return;
            }

            let txt_content = data
                .map(row => row.export_line || "")
                .join("\r\n");

            let blob = new Blob(
                [txt_content],
                { type: "text/plain;charset=utf-8" }
            );

            let url = window.URL.createObjectURL(blob);

            let a = document.createElement("a");
            a.href = url;
            a.download = "bank_export.txt";
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);

            window.URL.revokeObjectURL(url);
        });
    }
};
