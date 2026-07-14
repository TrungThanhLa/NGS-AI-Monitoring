import { App, Button, Card, Col, Form, InputNumber, Row, Switch } from 'antd'
import PageHeader from '@/components/common/PageHeader'

export default function SystemSettings() {
  const [form] = Form.useForm()
  const { message } = App.useApp()

  const onSave = () => {
    message.success('Lưu cài đặt thành công')
  }

  return (
    <div>
      <PageHeader
        title="Cài đặt hệ thống"
        breadcrumbs={[{ title: 'Tổng quan', href: '/' }, { title: 'Cấu hình hệ thống' }, { title: 'Cài đặt' }]}
      />

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}>
          <Card title="Cài đặt xác thực" style={{ borderRadius: 12 }}>
            <Form form={form} layout="vertical" onFinish={onSave}>
              <Form.Item name="max_login_attempts" label="Số lần đăng nhập sai tối đa" initialValue={5}>
                <InputNumber min={1} max={20} style={{ width: '100%' }} />
              </Form.Item>
              <Form.Item name="lockout_minutes" label="Thời gian khóa (phút)" initialValue={30}>
                <InputNumber min={5} max={1440} style={{ width: '100%' }} />
              </Form.Item>
              <Form.Item name="session_minutes" label="Thời hạn phiên làm việc (phút)" initialValue={60}>
                <InputNumber min={15} max={480} style={{ width: '100%' }} />
              </Form.Item>
              <Form.Item>
                <Button type="primary" htmlType="submit">Lưu cài đặt</Button>
              </Form.Item>
            </Form>
          </Card>
        </Col>

        <Col xs={24} lg={12}>
          <Card title="Cài đặt crawler" style={{ borderRadius: 12 }}>
            <Form layout="vertical" onFinish={onSave}>
              <Form.Item name="default_interval" label="Chu kỳ thu thập mặc định (phút)" initialValue={60}>
                <InputNumber min={5} max={1440} style={{ width: '100%' }} />
              </Form.Item>
              <Form.Item name="max_concurrent" label="Số luồng thu thập đồng thời" initialValue={5}>
                <InputNumber min={1} max={20} style={{ width: '100%' }} />
              </Form.Item>
              <Form.Item name="timeout" label="Timeout (giây)" initialValue={30}>
                <InputNumber min={5} max={120} style={{ width: '100%' }} />
              </Form.Item>
              <Form.Item name="enabled" label="Bật crawler" valuePropName="checked" initialValue={true}>
                <Switch />
              </Form.Item>
              <Form.Item>
                <Button type="primary" htmlType="submit">Lưu cài đặt</Button>
              </Form.Item>
            </Form>
          </Card>
        </Col>
      </Row>
    </div>
  )
}
