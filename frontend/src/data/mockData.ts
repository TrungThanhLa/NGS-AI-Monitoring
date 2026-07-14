// ─────────────────────────────────────────────────────────────────────────────
// Demo seed data — NGS Monitor
// ─────────────────────────────────────────────────────────────────────────────

export const DEMO_USER = {
  id: 'u-admin-001',
  username: 'admin',
  full_name: 'Nguyễn Văn Admin',
  email: 'admin@ngs.vn',
  permissions: [
    'user.view','user.create','user.update','user.delete',
    'role.view','role.create','role.update','role.delete',
    'campaign.view','campaign.create','campaign.update','campaign.delete','campaign.manage',
    'source.view','source.create','source.update','source.delete',
    'content.view','content.update',
    'alert.view','alert.manage',
    'case.view','case.create','case.update',
    'report.view','report.create',
    'audit_log.view',
    'system.configure',
  ],
}

// ─── Platforms ────────────────────────────────────────────────────────────────
export const platforms = [
  { id: 'p-1', code: 'WEBSITE',  name: 'Website / Cổng thông tin', apiRequired: false, apiDocs: '' },
  { id: 'p-2', code: 'FACEBOOK', name: 'Facebook',  apiRequired: true,  apiDocs: 'https://developers.facebook.com/tools/explorer/' },
  { id: 'p-3', code: 'YOUTUBE',  name: 'YouTube',   apiRequired: true,  apiDocs: 'https://console.cloud.google.com' },
  { id: 'p-4', code: 'TIKTOK',   name: 'TikTok',    apiRequired: true,  apiDocs: 'https://developers.tiktok.com/products/research-api/' },
  { id: 'p-5', code: 'ZALO',     name: 'Zalo',      apiRequired: true,  apiDocs: 'https://developers.zalo.me/' },
  { id: 'p-6', code: 'RSS',      name: 'RSS Feed',  apiRequired: false, apiDocs: '' },
  { id: 'p-7', code: 'TELEGRAM', name: 'Telegram',  apiRequired: true,  apiDocs: 'https://my.telegram.org' },
]

const pMap: Record<string, typeof platforms[0]> = Object.fromEntries(platforms.map(p => [p.code, p]))

// ─── Source Categories ────────────────────────────────────────────────────────
export const sourceCategories = [
  { id: 'cat-1', code: 'GOV',          name: 'Cơ quan nhà nước' },
  { id: 'cat-2', code: 'ANTI_FAKE',    name: 'Hệ thống chống tin giả' },
  { id: 'cat-3', code: 'MEDIA',        name: 'Cơ quan báo chí chủ lực' },
  { id: 'cat-4', code: 'SOCIAL_MEDIA', name: 'Mạng xã hội / Kênh truyền thông' },
]

const cMap: Record<string, typeof sourceCategories[0]> = Object.fromEntries(sourceCategories.map(c => [c.code, c]))

// ─── 40 Nguồn dữ liệu thực tế ────────────────────────────────────────────────
function makeSource(
  id: string, no: number, group: string,
  name: string, url: string,
  platform: string, category: string,
  freq: number, notes: string | null = null,
) {
  const lastCrawled = new Date(Date.now() - Math.floor(Math.random() * 6 * 3600000))
  return {
    id,
    no,
    group,
    name,
    url,
    status: 'ACTIVE' as const,
    crawl_frequency: freq,
    last_crawled_at: lastCrawled.toISOString(),
    notes,
    is_active: true,
    created_at: '2026-01-01T08:00:00',
    updated_at: '2026-01-01T08:00:00',
    platform: pMap[platform],
    category: cMap[category],
  }
}

export const sources = [
  // ── 3.1 Nhóm kênh của Chính phủ (Văn phòng Chính phủ) ──────────────────
  makeSource('s-01',  1, '3.1 – Chính phủ', 'Cổng Thông tin điện tử Chính phủ Việt Nam',           'https://chinhphu.vn',                                                   'WEBSITE',  'GOV',          300,  null),
  makeSource('s-02',  2, '3.1 – Chính phủ', 'Facebook Thông tin Chính phủ (tiếng Việt)',            'https://www.facebook.com/thongtinchinhphu',                             'FACEBOOK', 'SOCIAL_MEDIA', 900,  null),
  makeSource('s-03',  3, '3.1 – Chính phủ', 'Facebook Vietnam Government Portal (tiếng Anh)',       'https://www.facebook.com/VNGov',                                        'FACEBOOK', 'SOCIAL_MEDIA', 900,  null),
  makeSource('s-04',  4, '3.1 – Chính phủ', 'TikTok Chính phủ Việt Nam',                           'https://www.tiktok.com/@chinhphu.vn',                                   'TIKTOK',   'SOCIAL_MEDIA', 1800, null),
  makeSource('s-05',  5, '3.1 – Chính phủ', 'YouTube Thông tin Chính phủ',                         'https://www.youtube.com/channel/UCYUxsH8xyKAQx1WpCcex5LA',             'YOUTUBE',  'SOCIAL_MEDIA', 1800, null),
  makeSource('s-06',  6, '3.1 – Chính phủ', 'Zalo Chính phủ Việt Nam (Official Account)',           'https://zalo.me/chinhphu',                                              'ZALO',     'SOCIAL_MEDIA', 1800, 'Tài khoản Zalo đã xác minh'),

  // ── 3.2 Nhóm kênh của Bộ VHTTDL ─────────────────────────────────────────
  makeSource('s-07',  7, '3.2 – Bộ VHTTDL',  'Cổng Thông tin điện tử Bộ VHTTDL',                  'https://bvhttdl.gov.vn',                                                'WEBSITE',  'GOV',          300,  null),
  makeSource('s-08',  8, '3.2 – Bộ VHTTDL',  'Trung tâm Xử lý Tin giả Việt Nam',                  'https://tingia.gov.vn',                                                 'WEBSITE',  'ANTI_FAKE',    300,  'Hệ thống xử lý tin giả quốc gia'),
  makeSource('s-09',  9, '3.2 – Bộ VHTTDL',  'Facebook Cổng Thông tin Bộ VHTTDL',                 'https://www.facebook.com/congthongtinbovhttdl',                         'FACEBOOK', 'SOCIAL_MEDIA', 900,  null),
  makeSource('s-10', 10, '3.2 – Bộ VHTTDL',  'Facebook Thông tin Văn hóa, Thể thao và Du lịch',   'https://www.facebook.com/thongtinvanhoathethaovadulich',                'FACEBOOK', 'SOCIAL_MEDIA', 900,  null),
  makeSource('s-11', 11, '3.2 – Bộ VHTTDL',  'Facebook Vietnam Anti Fake News',                    'https://www.facebook.com/vnantifakenews',                               'FACEBOOK', 'ANTI_FAKE',    900,  'Kênh chống tin giả chính thức'),

  // ── 3.3 Nhóm kênh của Bộ Quốc phòng ─────────────────────────────────────
  makeSource('s-12', 12, '3.3 – Bộ Quốc phòng', 'Cổng Thông tin điện tử Bộ Quốc phòng',          'https://mod.gov.vn',                                                    'WEBSITE',  'GOV',          300,  null),
  makeSource('s-13', 13, '3.3 – Bộ Quốc phòng', 'Báo Quân đội Nhân dân điện tử',                 'https://www.qdnd.vn',                                                   'WEBSITE',  'MEDIA',        300,  null),
  makeSource('s-14', 14, '3.3 – Bộ Quốc phòng', 'Facebook Truyền hình Quốc phòng VN (QPVN)',      'https://www.facebook.com/quocphongvietnamqpvn',                         'FACEBOOK', 'SOCIAL_MEDIA', 900,  null),
  makeSource('s-15', 15, '3.3 – Bộ Quốc phòng', 'YouTube Truyền hình Quốc phòng VN (QPVN)',       'https://www.youtube.com/channel/UCnOk3kjev4rLlkC6_jzXUfw',             'YOUTUBE',  'SOCIAL_MEDIA', 1800, null),

  // ── 3.4 Nhóm kênh của Bộ Công an ────────────────────────────────────────
  makeSource('s-16', 16, '3.4 – Bộ Công an',    'Cổng Thông tin điện tử Bộ Công an',              'https://bocongan.gov.vn',                                               'WEBSITE',  'GOV',          300,  null),
  makeSource('s-17', 17, '3.4 – Bộ Công an',    'Báo Công an Nhân dân điện tử',                   'https://cand.com.vn',                                                   'WEBSITE',  'MEDIA',        300,  null),
  makeSource('s-18', 18, '3.4 – Bộ Công an',    'Facebook Báo Công an Nhân dân',                  'https://www.facebook.com/baocongan',                                    'FACEBOOK', 'SOCIAL_MEDIA', 900,  null),
  makeSource('s-19', 19, '3.4 – Bộ Công an',    'Facebook ANTV – Truyền hình Công an Nhân dân',   'https://www.facebook.com/antv.gov.vn',                                  'FACEBOOK', 'SOCIAL_MEDIA', 900,  null),
  makeSource('s-20', 20, '3.4 – Bộ Công an',    'YouTube ANTV – Truyền hình Công an Nhân dân',    'https://www.youtube.com/@ANTVTruyenhinhCongan',                         'YOUTUBE',  'SOCIAL_MEDIA', 1800, null),
  makeSource('s-21', 21, '3.4 – Bộ Công an',    'TikTok ANTV News',                               'https://www.tiktok.com/@antvnews',                                      'TIKTOK',   'SOCIAL_MEDIA', 1800, null),

  // ── 3.5 Nhóm cơ quan báo chí chủ lực – VTV ──────────────────────────────
  makeSource('s-22', 22, '3.5 – VTV',            'Cổng Thông tin Đài Truyền hình Việt Nam',        'https://vtv.gov.vn',                                                    'WEBSITE',  'GOV',          300,  null),
  makeSource('s-23', 23, '3.5 – VTV',            'Báo điện tử VTV News',                           'https://vtv.vn',                                                        'WEBSITE',  'MEDIA',        300,  null),
  makeSource('s-24', 24, '3.5 – VTV',            'VTV – Chuyên mục Tin giả',                       'https://vtv.vn/tin-gia.html',                                           'WEBSITE',  'ANTI_FAKE',    300,  'Chuyên mục chống tin giả của VTV'),
  makeSource('s-25', 25, '3.5 – VTV',            'VTV – Chuyên mục Thông tin giả mạo',             'https://vtv.vn/thong-tin-gia-mao.html',                                 'WEBSITE',  'ANTI_FAKE',    300,  null),
  makeSource('s-26', 26, '3.5 – VTV',            'VTV – Chuyên mục Báo tin giả',                   'https://vtv.vn/bao-tin-gia.html',                                       'WEBSITE',  'ANTI_FAKE',    300,  null),
  makeSource('s-27', 27, '3.5 – VTV',            'Facebook VTV – Đài Truyền hình Việt Nam',        'https://www.facebook.com/VTVtoiyeu',                                    'FACEBOOK', 'SOCIAL_MEDIA', 900,  null),
  makeSource('s-28', 28, '3.5 – VTV',            'Facebook VTV24',                                  'https://www.facebook.com/tintucvtv24',                                  'FACEBOOK', 'SOCIAL_MEDIA', 900,  null),
  makeSource('s-29', 29, '3.5 – VTV',            'YouTube VTV24',                                   'https://www.youtube.com/@vtv24',                                        'YOUTUBE',  'SOCIAL_MEDIA', 1800, null),
  makeSource('s-30', 30, '3.5 – VTV',            'TikTok VTV24 News',                               'https://www.tiktok.com/@vtv24news',                                     'TIKTOK',   'SOCIAL_MEDIA', 1800, null),
  makeSource('s-31', 31, '3.5 – VTV',            'YouTube VTV4',                                    'https://www.youtube.com/channel/UCQ4JPrrur8XOuxNugXmc39g',             'YOUTUBE',  'SOCIAL_MEDIA', 1800, null),

  // ── 3.6 Nhóm cơ quan báo chí chủ lực – VOV ──────────────────────────────
  makeSource('s-32', 32, '3.6 – VOV',            'Cổng Thông tin Đài Tiếng nói Việt Nam',          'https://vov.vn',                                                        'WEBSITE',  'MEDIA',        300,  null),
  makeSource('s-33', 33, '3.6 – VOV',            'Facebook VOV1 – Thời sự Chính trị Tổng hợp',     'https://www.facebook.com/VOV1News',                                     'FACEBOOK', 'SOCIAL_MEDIA', 900,  null),
  makeSource('s-34', 34, '3.6 – VOV',            'YouTube VOV Digital',                             'https://www.youtube.com/@vovdigital',                                   'YOUTUBE',  'SOCIAL_MEDIA', 1800, null),
  makeSource('s-35', 35, '3.6 – VOV',            'TikTok VOV News',                                 'https://www.tiktok.com/@vovnews',                                       'TIKTOK',   'SOCIAL_MEDIA', 1800, null),

  // ── 3.7 Nhóm cơ quan báo chí chủ lực – TTXVN ───────────────────────────
  makeSource('s-36', 36, '3.7 – TTXVN',          'Cổng Thông tin Thông tấn xã Việt Nam',           'https://www.vnanet.vn',                                                 'WEBSITE',  'MEDIA',        300,  null),
  makeSource('s-37', 37, '3.7 – TTXVN',          'Báo điện tử VietnamPlus',                         'https://www.vietnamplus.vn',                                            'WEBSITE',  'MEDIA',        300,  null),
  makeSource('s-38', 38, '3.7 – TTXVN',          'Facebook VietnamPlus',                            'https://www.facebook.com/vietnamplus',                                  'FACEBOOK', 'SOCIAL_MEDIA', 900,  null),
  makeSource('s-39', 39, '3.7 – TTXVN',          'YouTube VietnamPlus',                             'https://www.youtube.com/@vietnamplus',                                  'YOUTUBE',  'SOCIAL_MEDIA', 1800, null),
  makeSource('s-40', 40, '3.7 – TTXVN',          'TikTok VietnamPlus News',                         'https://www.tiktok.com/@vietnamplusnews',                               'TIKTOK',   'SOCIAL_MEDIA', 1800, null),
]

// ─── Roles ────────────────────────────────────────────────────────────────────
export const roles = [
  { id: 'r-1', code: 'ADMIN',    name: 'Quản trị hệ thống',   description: 'Toàn quyền truy cập và quản trị hệ thống',       is_system: true,  status: 'ACTIVE',   user_count: 5,  created_at: '2026-06-16T09:15:00', permissions: [] },
  { id: 'r-2', code: 'EDITOR',   name: 'Biên tập viên',        description: 'Thêm, sửa, duyệt và xuất bản nội dung',          is_system: true,  status: 'ACTIVE',   user_count: 12, created_at: '2026-06-16T09:20:00', permissions: [] },
  { id: 'r-3', code: 'VIEWER',   name: 'Người xem',            description: 'Xem dữ liệu và báo cáo',                         is_system: true,  status: 'ACTIVE',   user_count: 18, created_at: '2026-06-16T09:25:00', permissions: [] },
  { id: 'r-4', code: 'AUDITOR',  name: 'Kiểm duyệt viên',      description: 'Xem và duyệt nội dung trước khi xuất bản',       is_system: true,  status: 'ACTIVE',   user_count: 7,  created_at: '2026-06-16T09:30:00', permissions: [] },
  { id: 'r-5', code: 'OPERATOR', name: 'Nhân viên vận hành',   description: 'Theo dõi hệ thống, xử lý cảnh báo',              is_system: false, status: 'SUSPENDED',user_count: 10, created_at: '2026-06-16T09:35:00', permissions: [] },
  { id: 'r-6', code: 'GUEST',    name: 'Khách',                 description: 'Truy cập giới hạn (chỉ một số chức năng)',       is_system: false, status: 'INACTIVE', user_count: 3,  created_at: '2026-06-16T09:40:00', permissions: [] },
]

// ─── Users ────────────────────────────────────────────────────────────────────
const ROLES = {
  ADMIN:    { id: 'r-1', code: 'ADMIN',    name: 'Quản trị hệ thống' },
  EDITOR:   { id: 'r-2', code: 'EDITOR',   name: 'Biên tập viên' },
  MONITOR:  { id: 'r-3', code: 'MONITOR',  name: 'Giám sát viên' },
  STAFF:    { id: 'r-4', code: 'STAFF',    name: 'Nhân viên' },
}

export const users = [
  { id: 'u-001', username: 'nguyenvana',    email: 'nguyenvana@dcv.vn',    phone: '0912345678', full_name: 'Nguyễn Văn A',      avatar_color: '#00859A', initials: 'NA', status: 'ACTIVE',  last_login_at: '2026-06-16T10:15:00', failed_login_count: 0, is_active: true,  created_at: '2026-01-01T00:00:00', roles: [ROLES.ADMIN],   is_me: true },
  { id: 'u-002', username: 'tranquangminh', email: 'tqm@dcv.vn',           phone: '0987001001', full_name: 'Trần Quang Minh',   avatar_color: '#00859A', initials: 'TQ', status: 'ACTIVE',  last_login_at: '2026-06-16T09:42:00', failed_login_count: 0, is_active: true,  created_at: '2026-01-05T00:00:00', roles: [ROLES.ADMIN],   is_me: false },
  { id: 'u-003', username: 'phamhoangnam',  email: 'phn@dcv.vn',           phone: '0987001002', full_name: 'Phạm Hoàng Nam',    avatar_color: '#52c41a', initials: 'PH', status: 'ACTIVE',  last_login_at: '2026-06-16T08:30:00', failed_login_count: 0, is_active: true,  created_at: '2026-01-10T00:00:00', roles: [ROLES.EDITOR],  is_me: false },
  { id: 'u-004', username: 'lethihuong',    email: 'lth@dcv.vn',           phone: '0987001003', full_name: 'Lê Thị Hương',      avatar_color: '#722ed1', initials: 'LT', status: 'ACTIVE',  last_login_at: '2026-06-15T17:20:00', failed_login_count: 0, is_active: true,  created_at: '2026-01-15T00:00:00', roles: [ROLES.MONITOR], is_me: false },
  { id: 'u-005', username: 'hoangducanh',   email: 'hda@dcv.vn',           phone: '0987001004', full_name: 'Hoàng Đức Anh',     avatar_color: '#fa8c16', initials: 'HD', status: 'ACTIVE',  last_login_at: '2026-06-15T16:05:00', failed_login_count: 0, is_active: true,  created_at: '2026-01-20T00:00:00', roles: [ROLES.STAFF],   is_me: false },
  { id: 'u-006', username: 'nguyenthutrang',email: 'ntt@dcv.vn',           phone: '0987001005', full_name: 'Nguyễn Thu Trang',  avatar_color: '#00859A', initials: 'NT', status: 'LOCKED',  last_login_at: '2026-06-14T11:10:00', failed_login_count: 5, is_active: false, created_at: '2026-02-01T00:00:00', roles: [ROLES.EDITOR],  is_me: false },
  { id: 'u-007', username: 'vukhachuy',     email: 'vkh@dcv.vn',           phone: '0987001006', full_name: 'Vũ Khắc Huy',       avatar_color: '#52c41a', initials: 'VK', status: 'ACTIVE',  last_login_at: '2026-06-14T10:00:00', failed_login_count: 0, is_active: true,  created_at: '2026-02-05T00:00:00', roles: [ROLES.STAFF],   is_me: false },
  { id: 'u-008', username: 'daothimai',     email: 'dtm@dcv.vn',           phone: '0987001007', full_name: 'Đào Thị Mai',        avatar_color: '#8C95A0', initials: 'DT', status: 'ACTIVE',  last_login_at: '2026-06-13T14:55:00', failed_login_count: 0, is_active: true,  created_at: '2026-02-10T00:00:00', roles: [ROLES.MONITOR], is_me: false },
  { id: 'u-009', username: 'nguyenvanbinh', email: 'nvb@dcv.vn',           phone: '0987001008', full_name: 'Nguyễn Văn Bình',   avatar_color: '#1677ff', initials: 'NB', status: 'ACTIVE',  last_login_at: '2026-06-13T09:30:00', failed_login_count: 0, is_active: true,  created_at: '2026-02-15T00:00:00', roles: [ROLES.EDITOR],  is_me: false },
  { id: 'u-010', username: 'tranthilan',    email: 'ttl@dcv.vn',           phone: '0987001009', full_name: 'Trần Thị Lan',       avatar_color: '#eb2f96', initials: 'TL', status: 'ACTIVE',  last_login_at: '2026-06-12T15:20:00', failed_login_count: 0, is_active: true,  created_at: '2026-02-20T00:00:00', roles: [ROLES.STAFF],   is_me: false },
  { id: 'u-011', username: 'phamvanduc',    email: 'pvd@dcv.vn',           phone: '0987001010', full_name: 'Phạm Văn Đức',       avatar_color: '#fa8c16', initials: 'PD', status: 'ACTIVE',  last_login_at: '2026-06-12T08:45:00', failed_login_count: 0, is_active: true,  created_at: '2026-03-01T00:00:00', roles: [ROLES.MONITOR], is_me: false },
  { id: 'u-012', username: 'levanmanh',     email: 'lvm@dcv.vn',           phone: '0987001011', full_name: 'Lê Văn Mạnh',        avatar_color: '#722ed1', initials: 'LM', status: 'INACTIVE',last_login_at: '2026-05-30T11:00:00', failed_login_count: 0, is_active: false, created_at: '2026-03-05T00:00:00', roles: [ROLES.STAFF],   is_me: false },
  { id: 'u-013', username: 'hoangthibich',  email: 'htb@dcv.vn',           phone: '0987001012', full_name: 'Hoàng Thị Bích',     avatar_color: '#52c41a', initials: 'HB', status: 'ACTIVE',  last_login_at: '2026-06-11T16:30:00', failed_login_count: 0, is_active: true,  created_at: '2026-03-10T00:00:00', roles: [ROLES.EDITOR],  is_me: false },
  { id: 'u-014', username: 'dinhvanhung',   email: 'dvh@dcv.vn',           phone: '0987001013', full_name: 'Đinh Văn Hùng',      avatar_color: '#1677ff', initials: 'DH', status: 'ACTIVE',  last_login_at: '2026-06-11T10:10:00', failed_login_count: 0, is_active: true,  created_at: '2026-03-15T00:00:00', roles: [ROLES.MONITOR], is_me: false },
  { id: 'u-015', username: 'buithibao',     email: 'btb@dcv.vn',           phone: '0987001014', full_name: 'Bùi Thị Bảo',        avatar_color: '#eb2f96', initials: 'BB', status: 'ACTIVE',  last_login_at: '2026-06-10T14:00:00', failed_login_count: 0, is_active: true,  created_at: '2026-03-20T00:00:00', roles: [ROLES.STAFF],   is_me: false },
  { id: 'u-016', username: 'vuthanhlong',   email: 'vtl@dcv.vn',           phone: '0987001015', full_name: 'Vũ Thành Long',      avatar_color: '#00859A', initials: 'VL', status: 'LOCKED',  last_login_at: '2026-06-08T09:00:00', failed_login_count: 3, is_active: false, created_at: '2026-04-01T00:00:00', roles: [ROLES.EDITOR],  is_me: false },
  { id: 'u-017', username: 'nguyenthingoc', email: 'ntn@dcv.vn',           phone: '0987001016', full_name: 'Nguyễn Thị Ngọc',   avatar_color: '#722ed1', initials: 'NN', status: 'ACTIVE',  last_login_at: '2026-06-10T08:30:00', failed_login_count: 0, is_active: true,  created_at: '2026-04-05T00:00:00', roles: [ROLES.STAFF],   is_me: false },
  { id: 'u-018', username: 'dothanhtuan',   email: 'dtt@dcv.vn',           phone: '0987001017', full_name: 'Đỗ Thành Tuấn',      avatar_color: '#fa8c16', initials: 'DT', status: 'ACTIVE',  last_login_at: '2026-06-09T13:45:00', failed_login_count: 0, is_active: true,  created_at: '2026-04-10T00:00:00', roles: [ROLES.MONITOR], is_me: false },
  { id: 'u-019', username: 'maivanquang',   email: 'mvq@dcv.vn',           phone: '0987001018', full_name: 'Mai Văn Quang',      avatar_color: '#52c41a', initials: 'MQ', status: 'ACTIVE',  last_login_at: '2026-06-09T10:20:00', failed_login_count: 0, is_active: true,  created_at: '2026-04-15T00:00:00', roles: [ROLES.EDITOR],  is_me: false },
  { id: 'u-020', username: 'phamthioanh',   email: 'pta@dcv.vn',           phone: '0987001019', full_name: 'Phạm Thị Oanh',      avatar_color: '#1677ff', initials: 'PA', status: 'ACTIVE',  last_login_at: '2026-06-08T15:30:00', failed_login_count: 0, is_active: true,  created_at: '2026-04-20T00:00:00', roles: [ROLES.STAFF],   is_me: false },
  { id: 'u-021', username: 'trinhvanthang', email: 'tvt@dcv.vn',           phone: '0987001020', full_name: 'Trịnh Văn Thắng',   avatar_color: '#8C95A0', initials: 'TT', status: 'INACTIVE',last_login_at: '2026-05-20T09:00:00', failed_login_count: 0, is_active: false, created_at: '2026-05-01T00:00:00', roles: [ROLES.MONITOR], is_me: false },
  { id: 'u-022', username: 'lydinhkhoa',    email: 'ldk@dcv.vn',           phone: '0987001021', full_name: 'Lý Đình Khoa',       avatar_color: '#722ed1', initials: 'LK', status: 'ACTIVE',  last_login_at: '2026-06-07T11:00:00', failed_login_count: 0, is_active: true,  created_at: '2026-05-05T00:00:00', roles: [ROLES.EDITOR],  is_me: false },
  { id: 'u-023', username: 'ngothithuy',    email: 'ntt2@dcv.vn',          phone: '0987001022', full_name: 'Ngô Thị Thúy',       avatar_color: '#eb2f96', initials: 'NT', status: 'ACTIVE',  last_login_at: '2026-06-06T14:15:00', failed_login_count: 0, is_active: true,  created_at: '2026-05-10T00:00:00', roles: [ROLES.STAFF],   is_me: false },
  { id: 'u-024', username: 'caoductrong',   email: 'cdt@dcv.vn',           phone: '0987001023', full_name: 'Cao Đức Trọng',      avatar_color: '#00859A', initials: 'CT', status: 'ACTIVE',  last_login_at: '2026-06-05T09:30:00', failed_login_count: 0, is_active: true,  created_at: '2026-05-15T00:00:00', roles: [ROLES.MONITOR], is_me: false },
]

// ─── Campaigns ────────────────────────────────────────────────────────────────
const SURVEY_KEYWORDS = [
  { keyword_id: 'kw-1', keyword: 'Tin giả và thông tin sai lệch' },
  { keyword_id: 'kw-2', keyword: 'Phản bác, đính chính thông tin' },
  { keyword_id: 'kw-3', keyword: 'Kiểm chứng và xác thực thông tin' },
  { keyword_id: 'kw-4', keyword: 'Giải thích chính sách và cung cấp thông tin chính thống' },
  { keyword_id: 'kw-5', keyword: 'Cảnh báo lừa đảo, giả mạo trên không gian mạng' },
  { keyword_id: 'kw-6', keyword: 'Trí tuệ nhân tạo (AI), Deepfake và các công nghệ tạo sinh' },
  { keyword_id: 'kw-7', keyword: 'An toàn thông tin và an ninh mạng' },
  { keyword_id: 'kw-8', keyword: 'Hướng dẫn nhận diện tin giả và nâng cao kỹ năng truyền thông số cho công chúng' },
]

export const campaigns = [
  {
    id: 'c-survey-2026',
    code: 'CMP-2026-SURVEY-01',
    name: 'Khảo sát truyền thông phòng, chống tin giả 01/01/2026 – 30/5/2026',
    description: 'Khảo sát, phân tích hoạt động truyền thông phòng, chống tin giả và thông tin sai lệch trên các kênh chính thống của Chính phủ, Bộ VHTTDL, Bộ Quốc phòng, Bộ Công an, VTV, VOV, TTXVN trong giai đoạn 01/01/2026 – 30/5/2026.',
    status: 'COMPLETED',
    owner_id: 'u-002',
    owner_name: 'Trần Thị Manager',
    start_date: '2026-01-01',
    end_date: '2026-05-30',
    is_active: true,
    created_at: '2025-12-20T08:00:00',
    updated_at: '2026-06-01T10:00:00',
  },
  {
    id: 'c-2',
    code: 'CMP-2026-002',
    name: 'Giám sát thông tin kinh tế – tài chính',
    description: 'Giám sát tin tức kinh tế, tài chính, thị trường chứng khoán và các sự kiện kinh tế lớn.',
    status: 'ACTIVE',
    owner_id: 'u-002',
    owner_name: 'Trần Thị Manager',
    start_date: '2026-02-01',
    end_date: null,
    is_active: true,
    created_at: '2026-02-01T08:00:00',
    updated_at: '2026-05-15T09:00:00',
  },
  {
    id: 'c-3',
    code: 'CMP-2026-003',
    name: 'Giám sát an ninh mạng & deepfake',
    description: 'Phát hiện nội dung deepfake, tấn công mạng và các mối đe dọa an ninh thông tin.',
    status: 'ACTIVE',
    owner_id: 'u-admin-001',
    owner_name: 'Nguyễn Văn Admin',
    start_date: '2026-03-01',
    end_date: null,
    is_active: true,
    created_at: '2026-03-01T08:00:00',
    updated_at: '2026-06-10T11:00:00',
  },
]

// Campaign detail (with keywords & sources) for the survey campaign
export const surveyDetail = {
  ...campaigns[0],
  keywords: SURVEY_KEYWORDS,
  sources: sources.map(s => ({ source_id: s.id, source_name: s.name })),
}

// ─── Contents (mock — referencing real sources) ───────────────────────────────
const TITLES = [
  'Cảnh báo: Xuất hiện tin giả về chính sách tăng lương hưu trên mạng xã hội',
  'Bộ Công an khuyến cáo thủ đoạn lừa đảo mạo danh công an, cán bộ nhà nước',
  'VTV bác bỏ thông tin sai sự thật về dịch bệnh đang lan truyền trên TikTok',
  'Trung tâm Xử lý Tin giả: Đã gỡ bỏ 1.200 bài đăng vi phạm trong tháng 5',
  'Deepfake giả giọng Thủ tướng xuất hiện, cơ quan chức năng vào cuộc điều tra',
  'VOV giải thích chính sách thuế thu nhập cá nhân — đính chính thông tin sai lệch',
  'Quân đội Nhân dân: Phản bác luận điệu xuyên tạc về chủ quyền biển đảo',
  'TTXVN xác thực: Hình ảnh về lũ lụt miền Bắc bị chỉnh sửa lan truyền sai sự thật',
  'Bộ VHTTDL hướng dẫn nhận diện tài khoản giả mạo cơ quan nhà nước',
  'VTV24: AI tạo sinh đang bị lợi dụng để tạo nội dung thất thiệt quy mô lớn',
  'Chính phủ ban hành quy định mới về xử lý tin giả trong không gian mạng',
  'Cảnh báo chiêu trò lừa đảo đầu tư tiền điện tử qua Telegram và Zalo',
]
const SENTIMENTS = ['POSITIVE','NEGATIVE','NEUTRAL','MIXED'] as const
const ATTENTION  = ['LOW','MEDIUM','HIGH','CRITICAL'] as const
const STATUSES   = ['NEW','REVIEWED','NEED_VERIFY','VERIFIED','NOT_RELEVANT'] as const

export const contents = Array.from({ length: 40 }, (_, i) => {
  const src = sources[i % sources.length]
  return {
    id: `cnt-${i + 1}`,
    url: `${src.url}/bai-viet-${1000 + i}`,
    title: TITLES[i % TITLES.length],
    summary: 'Tóm tắt nội dung bài viết liên quan đến công tác phòng, chống tin giả và thông tin sai lệch.',
    content: null,
    sentiment: SENTIMENTS[i % 4],
    attention_score: Math.min(100, 30 + (i * 7) % 70),
    attention_level: ATTENTION[i % 4],
    status: STATUSES[i % 5],
    published_at: new Date(Date.parse('2026-01-01') + i * 3 * 86400000).toISOString(),
    is_active: true,
    created_at: new Date(Date.parse('2026-01-01') + i * 3 * 86400000).toISOString(),
    updated_at: new Date(Date.parse('2026-01-01') + i * 3 * 86400000 + 3600000).toISOString(),
    source: { id: src.id, name: src.name, platform_code: src.platform?.code ?? null },
    campaign: { id: 'c-survey-2026', code: 'CMP-2026-SURVEY-01', name: 'Khảo sát truyền thông phòng, chống tin giả' },
    ai_analysis: {
      id: `ai-${i + 1}`,
      summary: 'Bài viết thuộc nhóm nội dung phòng, chống tin giả, đính chính và cung cấp thông tin chính thống.',
      sentiment: SENTIMENTS[i % 4],
      sentiment_score: +(0.55 + (i % 40) / 100).toFixed(2),
      attention_score: Math.min(100, 30 + (i * 7) % 70),
      persons: i % 3 === 0 ? ['Bộ trưởng Nguyễn Văn A'] : [],
      organizations: ['Bộ Công an', 'Trung tâm Xử lý Tin giả'][i % 2] ? [['Bộ Công an', 'Trung tâm Xử lý Tin giả'][i % 2]] : [],
      locations: ['Thành phố Hồ Chí Minh', 'Hà Nội', 'Việt Nam'][i % 3] ? [['Thành phố Hồ Chí Minh', 'Hà Nội', 'Việt Nam'][i % 3]] : [],
      needs_verification: i % 7 === 0,
    },
  }
})

// ─── Alerts ───────────────────────────────────────────────────────────────────
export const alerts = Array.from({ length: 12 }, (_, i) => ({
  id: `al-${i + 1}`,
  title: [
    '[CRITICAL] Deepfake giả giọng lãnh đạo — lan truyền trên 15 nền tảng',
    '[HIGH] Tin giả về chính sách lương hưu cần đính chính khẩn',
    '[CRITICAL] Tài khoản giả mạo Bộ Công an lừa đảo trên Telegram',
    '[HIGH] Video AI tạo sinh xuyên tạc phát biểu quan chức Chính phủ',
    '[MEDIUM] Thông tin sai lệch về dịch bệnh lan trên Facebook',
    '[HIGH] Scam đầu tư crypto giả danh TTXVN lan rộng trên Zalo',
  ][i % 6],
  alert_type: ['CRITICAL_ATTENTION','HIGH_RISK_TOPIC','NEEDS_VERIFICATION','HIGH_RISK_SCORE'][i % 4],
  severity:   ['CRITICAL','HIGH','MEDIUM','LOW'][i % 4],
  status:     ['OPEN','IN_PROGRESS','RESOLVED','CLOSED'][i % 4],
  content_id: contents[i].id,
  content_url: contents[i].url,
  content_title: contents[i].title,
  attention_score: 65 + i * 3,
  created_at: new Date(Date.parse('2026-01-15') + i * 10 * 86400000).toISOString(),
  updated_at: new Date(Date.parse('2026-01-15') + i * 10 * 86400000 + 7200000).toISOString(),
  resolved_at: i % 4 >= 2 ? new Date(Date.parse('2026-01-15') + i * 10 * 86400000 + 86400000).toISOString() : null,
  assigned_to: i % 3 === 0 ? { id: 'u-003', full_name: 'Lê Văn Analyst' } : null,
  notes: i % 4 === 3 ? 'Đã xử lý, chuyển thông tin đến cơ quan có thẩm quyền.' : null,
}))

// ─── Cases ────────────────────────────────────────────────────────────────────
export const cases = [
  { id: 'case-1', code: 'VV-2026-001', title: 'Điều tra deepfake giả giọng lãnh đạo Chính phủ', description: 'Phát hiện hàng loạt video deepfake giả giọng nói và hình ảnh của lãnh đạo cấp cao, lan truyền qua TikTok và YouTube kêu gọi đầu tư tài chính.', status: 'INVESTIGATING', priority: 'CRITICAL', created_by: { id: 'u-003', full_name: 'Lê Văn Analyst' }, assigned_to: { id: 'u-003', full_name: 'Lê Văn Analyst' }, alert_count: 5, content_count: 18, created_at: '2026-02-10T08:00:00', updated_at: '2026-06-01T14:00:00', closed_at: null },
  { id: 'case-2', code: 'VV-2026-002', title: 'Chiến dịch tin giả về chính sách lương hưu', description: 'Hàng loạt bài đăng sai lệch về điều chỉnh lương hưu lan truyền qua Facebook và Zalo, gây hoang mang trong cộng đồng người cao tuổi.', status: 'CONCLUDED', priority: 'HIGH', created_by: { id: 'u-003', full_name: 'Lê Văn Analyst' }, assigned_to: { id: 'u-002', full_name: 'Trần Thị Manager' }, alert_count: 3, content_count: 12, created_at: '2026-01-20T08:00:00', updated_at: '2026-03-15T10:00:00', closed_at: null },
  { id: 'case-3', code: 'VV-2026-003', title: 'Mạng lưới tài khoản giả mạo cơ quan nhà nước', description: 'Phát hiện mạng lưới tài khoản giả mạo Bộ Công an, Bộ VHTTDL hoạt động trên Telegram và Zalo để lừa đảo tài chính.', status: 'OPEN', priority: 'HIGH', created_by: { id: 'u-003', full_name: 'Lê Văn Analyst' }, assigned_to: null, alert_count: 4, content_count: 9, created_at: '2026-04-05T08:00:00', updated_at: '2026-06-20T09:00:00', closed_at: null },
  { id: 'case-4', code: 'VV-2026-004', title: 'Scam đầu tư giả danh TTXVN / VietnamPlus', description: 'Kẻ xấu giả mạo tên miền và logo TTXVN/VietnamPlus để phát tán thông tin sai lệch về các cơ hội đầu tư lừa đảo.', status: 'OPEN', priority: 'HIGH', created_by: { id: 'u-003', full_name: 'Lê Văn Analyst' }, assigned_to: { id: 'u-003', full_name: 'Lê Văn Analyst' }, alert_count: 2, content_count: 7, created_at: '2026-05-01T08:00:00', updated_at: '2026-06-15T11:00:00', closed_at: null },
]

// ─── Reports ──────────────────────────────────────────────────────────────────
export const reports = [
  { id: 'rep-1', title: 'Báo cáo tổng hợp Khảo sát truyền thông phòng, chống tin giả (01/01 – 30/5/2026)', report_type: 'CAMPAIGN', status: 'DRAFT', period_from: '2026-01-01', period_to: '2026-05-30', created_by: { id: 'u-002', full_name: 'Trần Thị Manager' }, created_at: '2026-06-01T08:00:00', updated_at: '2026-06-15T10:00:00', published_at: null },
  { id: 'rep-2', title: 'Báo cáo tháng 5/2026 — Tình hình tin giả và phản ứng thông tin chính thống',       report_type: 'MONTHLY',  status: 'PUBLISHED', period_from: '2026-05-01', period_to: '2026-05-31', created_by: { id: 'u-002', full_name: 'Trần Thị Manager' }, created_at: '2026-06-05T08:00:00', updated_at: '2026-06-10T10:00:00', published_at: '2026-06-10T10:00:00' },
  { id: 'rep-3', title: 'Báo cáo quý I/2026 — Phân tích xu hướng deepfake và AI tạo sinh',                  report_type: 'QUARTERLY',status: 'PUBLISHED', period_from: '2026-01-01', period_to: '2026-03-31', created_by: { id: 'u-002', full_name: 'Trần Thị Manager' }, created_at: '2026-04-05T08:00:00', updated_at: '2026-04-15T10:00:00', published_at: '2026-04-15T10:00:00' },
]

// ─── Audit Logs ───────────────────────────────────────────────────────────────
export const auditLogs = Array.from({ length: 20 }, (_, i) => ({
  id: `log-${i + 1}`,
  action:      ['LOGIN','CREATE','UPDATE','DELETE','VIEW','EXPORT'][i % 6],
  resource:    ['USER','CAMPAIGN','SOURCE','CONTENT','ALERT','CASE','REPORT'][i % 7],
  resource_id: `res-${i + 1}`,
  description: ['Đăng nhập thành công','Tạo mới chiến dịch','Cập nhật nguồn dữ liệu','Xóa người dùng','Xem báo cáo','Xuất dữ liệu'][i % 6],
  ip_address:  `192.168.1.${(i % 50) + 10}`,
  user_agent:  'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
  user:        { id: users[i % users.length].id, username: users[i % users.length].username, full_name: users[i % users.length].full_name },
  created_at:  new Date(Date.now() - i * 1800000).toISOString(),
}))

// ─── Jobs ─────────────────────────────────────────────────────────────────────
export const jobs = Array.from({ length: 20 }, (_, i) => {
  const src = sources[i % sources.length]
  return {
    id: `job-${i + 1}`,
    job_id: `rq-${Date.now()}-${i}`,
    source_id: src.id,
    source_name: src.name,
    status: ['SUCCESS','RUNNING','PENDING','FAILED','SUCCESS'][i % 5],
    records_found: i % 5 !== 3 ? Math.floor(10 + (i * 13) % 80) : 0,
    records_saved: i % 5 !== 3 ? Math.floor(5  + (i * 9)  % 50) : 0,
    error: i % 5 === 3 ? 'Connection timeout — nguồn không phản hồi sau 60s' : null,
    started_at: new Date(Date.now() - i * 3600000).toISOString(),
    finished_at: i % 5 !== 1 ? new Date(Date.now() - i * 3600000 + 120000).toISOString() : null,
    created_at: new Date(Date.now() - i * 3600000).toISOString(),
  }
})

// ─── Permissions ──────────────────────────────────────────────────────────────
export const permissions = [
  { id: 'perm-1',  code: 'user.view',        resource: 'user',      action: 'view',      description: 'Xem danh sách người dùng',       is_active: true },
  { id: 'perm-2',  code: 'user.create',      resource: 'user',      action: 'create',    description: 'Tạo người dùng mới',             is_active: true },
  { id: 'perm-3',  code: 'user.update',      resource: 'user',      action: 'update',    description: 'Cập nhật thông tin người dùng',  is_active: true },
  { id: 'perm-4',  code: 'user.delete',      resource: 'user',      action: 'delete',    description: 'Xóa người dùng',                 is_active: true },
  { id: 'perm-5',  code: 'role.view',        resource: 'role',      action: 'view',      description: 'Xem danh sách vai trò',          is_active: true },
  { id: 'perm-6',  code: 'role.create',      resource: 'role',      action: 'create',    description: 'Tạo vai trò mới',                is_active: true },
  { id: 'perm-7',  code: 'campaign.view',    resource: 'campaign',  action: 'view',      description: 'Xem chiến dịch',                 is_active: true },
  { id: 'perm-8',  code: 'campaign.create',  resource: 'campaign',  action: 'create',    description: 'Tạo chiến dịch',                 is_active: true },
  { id: 'perm-9',  code: 'campaign.manage',  resource: 'campaign',  action: 'manage',    description: 'Quản lý chiến dịch',             is_active: true },
  { id: 'perm-10', code: 'source.view',      resource: 'source',    action: 'view',      description: 'Xem nguồn dữ liệu',             is_active: true },
  { id: 'perm-11', code: 'source.create',    resource: 'source',    action: 'create',    description: 'Thêm nguồn dữ liệu',            is_active: true },
  { id: 'perm-12', code: 'content.view',     resource: 'content',   action: 'view',      description: 'Xem nội dung',                   is_active: true },
  { id: 'perm-13', code: 'alert.view',       resource: 'alert',     action: 'view',      description: 'Xem cảnh báo',                   is_active: true },
  { id: 'perm-14', code: 'alert.manage',     resource: 'alert',     action: 'manage',    description: 'Xử lý cảnh báo',                is_active: true },
  { id: 'perm-15', code: 'case.view',        resource: 'case',      action: 'view',      description: 'Xem vụ việc',                    is_active: true },
  { id: 'perm-16', code: 'case.create',      resource: 'case',      action: 'create',    description: 'Tạo vụ việc',                    is_active: true },
  { id: 'perm-17', code: 'report.view',      resource: 'report',    action: 'view',      description: 'Xem báo cáo',                    is_active: true },
  { id: 'perm-18', code: 'report.create',    resource: 'report',    action: 'create',    description: 'Tạo báo cáo',                    is_active: true },
  { id: 'perm-19', code: 'audit_log.view',   resource: 'audit_log', action: 'view',      description: 'Xem nhật ký hệ thống',          is_active: true },
  { id: 'perm-20', code: 'system.configure', resource: 'system',    action: 'configure', description: 'Cấu hình hệ thống',             is_active: true },
]

// ─── Connectors ───────────────────────────────────────────────────────────────
export const connectors = [
  {
    id: 'conn-website', platform: 'WEBSITE', name: 'Website Connector',
    method: 'Requests / BeautifulSoup', status: 'ACTIVE',
    api_key: null, token: null, fallback: 'Playwright',
    last_checked_at: '2026-06-16T10:15:00Z', success_rate: 98.3,
    config: { user_agent: 'NGSBot/1.0', timeout: '30' },
    description: 'Thu thập nội dung từ các trang web và cổng thông tin', created_at: '2026-01-01T00:00:00Z',
  },
  {
    id: 'conn-facebook', platform: 'FACEBOOK', name: 'Facebook Connector',
    method: 'Graph API / Page Public / Playwright', status: 'ACTIVE',
    api_key: 'EAAxxxxxxxxxxxxxxx', token: null, fallback: 'Có',
    last_checked_at: '2026-06-16T09:58:00Z', success_rate: 96.7,
    config: { app_id: '1234567890', app_secret: 'abc123secret', access_token: 'EAAxxxxxxxxxxxxxxx', api_version: 'v19.0' },
    description: 'Thu thập bài đăng từ fanpage Facebook qua Graph API v19.0', created_at: '2026-01-01T00:00:00Z',
  },
  {
    id: 'conn-youtube', platform: 'YOUTUBE', name: 'YouTube Connector',
    method: 'YouTube Data API v3', status: 'ACTIVE',
    api_key: 'AIzaSyXxxxxxxxxxxxxxxxx', token: null, fallback: 'Có',
    last_checked_at: '2026-06-16T10:05:00Z', success_rate: 97.1,
    config: { api_key: 'AIzaSyXxxxxxxxxxxxxxxxx' },
    description: 'Thu thập video và kênh YouTube, hỗ trợ @username URL', created_at: '2026-01-01T00:00:00Z',
  },
  {
    id: 'conn-tiktok', platform: 'TIKTOK', name: 'TikTok Connector',
    method: 'TikTok Research API', status: 'WARNING',
    api_key: 'tkt_xxxxxxxxxxxxxxxx', token: null, fallback: 'Playwright',
    last_checked_at: '2026-06-16T08:30:00Z', success_rate: 78.2,
    config: { client_key: 'tkt_xxxxxxxxxxxxxxxx', client_secret: 'secret_tiktok_xxx' },
    description: 'TikTok Research API + Playwright stealth fallback khi rate limit', created_at: '2026-01-01T00:00:00Z',
  },
  {
    id: 'conn-zalo', platform: 'ZALO', name: 'Zalo Connector',
    method: 'Zalo OA API / Manual Import', status: 'ACTIVE',
    api_key: null, token: 'zalo_oa_token_xxx', fallback: 'Có',
    last_checked_at: '2026-06-16T09:40:00Z', success_rate: 94.6,
    config: { app_id: 'zalo_app_001', secret_key: 'zalo_secret_xxx', access_token: 'zalo_oa_token_xxx' },
    description: 'Zalo OA API v2 — yêu cầu là chủ sở hữu OA', created_at: '2026-01-01T00:00:00Z',
  },
  {
    id: 'conn-rss', platform: 'RSS', name: 'RSS Connector',
    method: 'RSS/Atom Feed', status: 'ACTIVE',
    api_key: null, token: null, fallback: null,
    last_checked_at: '2026-06-16T09:50:00Z', success_rate: 100,
    config: {},
    description: 'Đọc RSS/Atom feed từ các báo điện tử và cổng thông tin', created_at: '2026-01-01T00:00:00Z',
  },
  {
    id: 'conn-telegram', platform: 'TELEGRAM', name: 'Telegram Connector',
    method: 'Telegram API', status: 'PAUSED',
    api_key: null, token: 'tg_session_xxx', fallback: 'Có',
    last_checked_at: '2026-06-15T16:20:00Z', success_rate: null,
    config: { api_id: '12345678', api_hash: 'abcdef1234567890', session_string: 'tg_session_xxx' },
    description: 'MTProto API — theo dõi kênh và nhóm Telegram', created_at: '2026-01-01T00:00:00Z',
  },
  {
    id: 'conn-manual', platform: 'MANUAL', name: 'Manual Import',
    method: 'File Upload / Manual Input', status: 'ACTIVE',
    api_key: null, token: null, fallback: null,
    last_checked_at: '2026-06-16T09:35:00Z', success_rate: 100,
    config: {},
    description: 'Nhập thủ công qua file Excel/CSV hoặc form nhập liệu', created_at: '2026-01-01T00:00:00Z',
  },
]

// ─── Connector Sources (derived from 40 real sources) ────────────────────────
// Maps the sources array into connector-source format for the split-panel UI
export const connectorSources = sources.map(s => ({
  id: `cs-${s.id}`,
  source_id: s.id,
  name: s.name,
  url: s.url,
  platform_code: s.platform?.code ?? 'WEBSITE',
  group: s.group,
  status: s.status,
  priority: s.no <= 10 ? 'HIGH' : s.no <= 25 ? 'MEDIUM' : 'LOW',
  method: (() => {
    const p = s.platform?.code
    if (p === 'FACEBOOK') return 'Graph API / Page Public / Playwright'
    if (p === 'YOUTUBE') return 'YouTube Data API v3'
    if (p === 'TIKTOK') return 'TikTok Research API'
    if (p === 'ZALO') return 'Zalo OA API / Manual Import'
    if (p === 'RSS') return 'RSS/Atom Feed'
    if (p === 'MANUAL') return 'File Upload / Manual Input'
    return 'Requests / BeautifulSoup'
  })(),
  // Fallback config
  fallback_method: (() => {
    const p = s.platform?.code
    if (p === 'WEBSITE' || p === 'TIKTOK') return 'PLAYWRIGHT'
    if (p === 'FACEBOOK' || p === 'YOUTUBE' || p === 'ZALO') return 'PLAYWRIGHT'
    return 'NONE'
  })(),
  fallback_max_retries: 3,
  fallback_delay_seconds: 15,
  fallback_triggers: ['HTTP_ERROR'],
  // Proxy config
  proxy_enabled: (() => {
    const p = s.platform?.code
    return p === 'WEBSITE' || p === 'TIKTOK'
  })(),
  proxy_mode: 'ROTATION',
  proxy_source: 'INTERNAL',
  proxy_pool: 'Website Pool 01',
  user_agent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
  timeout: 30,
  retry_count: 3,
  request_delay: '2 - 5',
  crawl_frequency: s.crawl_frequency,
  channel_id: (() => {
    const p = s.platform?.code
    if (p === 'FACEBOOK') { const m = s.url.match(/facebook\.com\/([^/?]+)/); return m?.[1] ?? null }
    if (p === 'YOUTUBE') { const m = s.url.match(/\/@([^/]+)|\/channel\/([^/]+)|\/user\/([^/]+)/); return m?.[1] ?? m?.[2] ?? m?.[3] ?? null }
    if (p === 'TIKTOK') { const m = s.url.match(/tiktok\.com\/@([^/]+)/); return m?.[1] ? `@${m[1]}` : null }
    return null
  })(),
  description: s.notes,
  notes: null,
  last_checked_at: s.last_crawled_at,
  success_rate: Math.floor(Math.random() * 15 + 85),
  created_at: s.created_at,
}))

// ─── Helper ───────────────────────────────────────────────────────────────────
export function paginate<T>(items: T[], page = 1, pageSize = 20) {
  const start = (page - 1) * pageSize
  return { items: items.slice(start, start + pageSize), total: items.length, page, page_size: pageSize }
}
