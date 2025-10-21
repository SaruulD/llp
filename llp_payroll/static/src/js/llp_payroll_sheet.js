/** @odoo-module */

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

class PayrollSheetField extends Component {
  static template = "llp_payroll.PayrollSheetField"; // match your XML t-name
  static props = { ...standardFieldProps };
  static supportedTypes = ["one2many"];

  setup() {
    this.orm = useService("orm");
    this.action = useService("action");
    this.state = {
      employees: [],
      rules: [],
      employee_values: {},
      employee_lines: {},
    };

    onWillStart(async () => {
      const sheetId = this.props.record?.resId;
      if (!sheetId) return;
      const data = await this.orm.call("llp.payroll.line", "get_line_values", [
        sheetId,
      ]);
      Object.assign(this.state, data);
    });
  }

  goToEmployee(id) {
    this.action.doAction({
      type: "ir.actions.act_window",
      res_model: "hr.employee",
      res_id: id,
      views: [[false, "form"]],
    });
  }
  goToRule(id) {
    this.action.doAction({
      type: "ir.actions.act_window",
      res_model: "llp.payroll.rule",
      res_id: id,
      views: [[false, "form"]],
    });
  }
}

registry.category("fields").add("payroll_sheet", {
  component: PayrollSheetField, // <- REQUIRED
  supportedTypes: ["one2many"], // optional (can also live on the class)
});
