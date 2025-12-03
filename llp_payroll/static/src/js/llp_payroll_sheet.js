/** @odoo-module */

import { Component, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

class PayrollSheetField extends Component {
  static template = "llp_payroll.PayrollSheetField";
  static props = { ...standardFieldProps };
  static supportedTypes = ["one2many"];

  setup() {
    this.orm = useService("orm");
    this.action = useService("action");
    this.formatMoney = (val, rule) => {
      if (rule.rulefield_type !== "digit") {
        return val ?? "";
      }
      if (typeof val === "string") {
        const maybeNum = Number(val);
        if (!isNaN(maybeNum) && val.trim() !== "") {
          return maybeNum.toLocaleString(undefined, {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
          });
        }
        return val;
      }

      if (typeof val === "number" && !isNaN(val)) {
        const n = Number(val) || 0;
        return n.toLocaleString(undefined, {
          minimumFractionDigits: 2,
          maximumFractionDigits: 2,
        });
      }

      return val ?? "";
    };

    this.goToEmployee = this.goToEmployee.bind(this);
    this.goToRule = this.goToRule.bind(this);
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
  component: PayrollSheetField,
  supportedTypes: ["one2many"],
});
