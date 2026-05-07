import { Card, CardContent, Typography } from "@mui/material";

export function DetailPlaceholder() {
  return (
    <Card>
      <CardContent>
        <Typography variant="h6">詳情頁（預留）</Typography>
        <Typography color="text.secondary">路由與版型已預留，下一個迭代會完成。</Typography>
      </CardContent>
    </Card>
  );
}

export function WhitelistAdminPlaceholder() {
  return (
    <Card>
      <CardContent>
        <Typography variant="h6">特殊人員名單管理頁（預留）</Typography>
        <Typography color="text.secondary">管理者介面將於下一個迭代實作。</Typography>
      </CardContent>
    </Card>
  );
}
