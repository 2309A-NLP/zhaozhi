const { createApp, ref, reactive, computed, onMounted, onBeforeUnmount } = Vue;

const ROLE_TYPE_LABELS = {
  assistant: "通用助手",
  friend: "虚拟朋友",
  doctor: "医生",
  custom: "自定义角色",
};

const DOMAIN_LABELS = {
  general: "通用",
  medical: "医疗",
  legal: "法律",
  finance: "金融",
  education: "教育",
  psychology: "心理",
  science: "科学",
  english: "英语",
};

const FALLBACK_ROLE = {
  id: 0,
  role_name: "通用助手",
  role_type: "assistant",
  personality: "专业、可靠、冷静，能够给出清晰稳定的回应。",
  language_style: "表达简洁、自然、礼貌，优先保证信息清楚。",
  constraints: "基于现有上下文回答，不编造事实。",
  knowledge_domains: ["general"],
  is_public: true,
};

function buildRoleView() {
  return {
    sessionId: "",
    draft: "",
    messages: [],
    lastDocs: [],
  };
}

createApp({
  setup() {
    const apiBase = ref(`${window.location.origin}/api`);
    const token = ref("");
    const currentUser = ref(null);
    const health = ref(null);
    const authMode = ref("login");
    const currentRoleId = ref(0);

    const authForm = reactive({
      username: "",
      password: "",
      confirmPassword: "",
      email: "",
    });

    const uploadForm = reactive({
      knowledgeDomain: "general",
      file: null,
    });

    const roleForm = reactive({
      roleName: "",
      roleType: "",
      personality: "",
      languageStyle: "",
      constraints: "",
      knowledgeDomainsText: "general",
      isPublic: false,
    });

    const state = reactive({
      roles: [],
      documents: [],
      roleViews: {},
      error: "",
      success: "",
    });

    const isAuthed = computed(() => !!token.value && !!currentUser.value);
    const allRoles = computed(() => state.roles);
    const currentRole = computed(
      () =>
        allRoles.value.find((role) => Number(role.id) === Number(currentRoleId.value)) ||
        allRoles.value[0] ||
        FALLBACK_ROLE,
    );
    const currentRoleView = computed(() => ensureRoleView(currentRoleId.value));
    const currentRoleDomainLabels = computed(() =>
      (currentRole.value.knowledge_domains || ["general"]).map(getDomainLabel),
    );
    const currentRoleDocuments = computed(() => {
      const domains = currentRole.value.knowledge_domains || ["general"];
      return state.documents.filter((doc) => {
        const domain = doc.knowledge_domain || "general";
        return domains.includes(domain) || currentRole.value.id === 0;
      });
    });
    const currentRoleTitle = computed(() => getRoleTypeLabel(currentRole.value.role_type));

    function getRoleKey(roleId) {
      return String(Number(roleId) || 0);
    }

    function ensureRoleView(roleId) {
      const key = getRoleKey(roleId);
      if (!state.roleViews[key]) {
        state.roleViews[key] = buildRoleView();
      }
      return state.roleViews[key];
    }

    function resetNotice() {
      state.error = "";
      state.success = "";
    }

    function getDomainLabel(domain) {
      return DOMAIN_LABELS[domain] || domain || "通用";
    }

    function getRoleTypeLabel(roleType) {
      return ROLE_TYPE_LABELS[roleType] || roleType || "角色";
    }

    function formatDomains(domains) {
      const items = (domains || ["general"]).map(getDomainLabel);
      return items.join(" / ");
    }

    function parseKnowledgeDomains(value) {
      return value
        .replaceAll("，", ",")
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean);
    }

    function parseRoleHash() {
      const match = window.location.hash.match(/^#\/roles\/(\d+)$/);
      return match ? Number(match[1]) : 0;
    }

    function syncRoleFromHash() {
      const requestedRoleId = parseRoleHash();
      const validIds = new Set(allRoles.value.map((role) => Number(role.id)));
      const firstRoleId = allRoles.value.length ? Number(allRoles.value[0].id) : 0;
      currentRoleId.value = validIds.has(requestedRoleId) ? requestedRoleId : firstRoleId;
      ensureRoleView(currentRoleId.value);
    }

    function navigateToRole(roleId) {
      const targetRoleId = Number(roleId) || 0;
      const nextHash = `#/roles/${targetRoleId}`;
      if (window.location.hash === nextHash) {
        currentRoleId.value = targetRoleId;
        ensureRoleView(targetRoleId);
        return;
      }
      window.location.hash = nextHash;
    }

    async function request(path, options = {}) {
      const headers = Object.assign({}, options.headers || {});
      if (token.value) {
        headers.Authorization = `Bearer ${token.value}`;
      }

      const response = await fetch(`${apiBase.value}${path}`, {
        ...options,
        headers,
      });

      const text = await response.text();
      let data = null;
      if (text) {
        try {
          data = JSON.parse(text);
        } catch {
          data = { message: text };
        }
      }

      if (!response.ok) {
        throw new Error(data?.detail || data?.message || `HTTP ${response.status}`);
      }

      return data;
    }

    async function runAction(action) {
      try {
        resetNotice();
        await action();
      } catch (error) {
        state.error = error instanceof Error ? error.message : String(error);
      }
    }

    async function loadHealth() {
      try {
        const response = await fetch(`${window.location.origin}/health`);
        health.value = await response.json();
      } catch {
        health.value = null;
      }
    }

    async function loadWorkspaceData() {
      state.roles = await request("/roles/");
      state.documents = await request("/documents/");
      syncRoleFromHash();
    }

    async function register() {
      await runAction(async () => {
        if (authForm.password !== authForm.confirmPassword) {
          throw new Error("两次输入的密码不一致。");
        }

        await request("/auth/register", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            username: authForm.username,
            password: authForm.password,
            email: authForm.email || null,
          }),
        });

        state.success = "注册成功，请使用账号密码登录。";
        authMode.value = "login";
      });
    }

    async function login() {
      await runAction(async () => {
        const body = new URLSearchParams({
          username: authForm.username,
          password: authForm.password,
        });

        const response = await fetch(`${apiBase.value}/auth/token`, {
          method: "POST",
          headers: { "Content-Type": "application/x-www-form-urlencoded" },
          body,
        });

        const data = await response.json();
        if (!response.ok) {
          throw new Error(data?.detail || "登录失败。");
        }

        token.value = data.access_token;
        currentUser.value = await request("/auth/me");
        await loadWorkspaceData();
        syncRoleFromHash();
      });
    }

    function logout() {
      token.value = "";
      currentUser.value = null;
      state.roles = [];
      state.documents = [];
      state.roleViews = {};
      currentRoleId.value = 0;
      resetNotice();
      navigateToRole(0);
    }

    async function createRole() {
      await runAction(async () => {
        if (!roleForm.roleName.trim()) {
          throw new Error("角色名称不能为空。");
        }

        const role = await request("/roles/", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            role_name: roleForm.roleName.trim(),
            role_type: roleForm.roleType.trim() || "custom",
            personality: roleForm.personality.trim() || null,
            language_style: roleForm.languageStyle.trim() || null,
            constraints: roleForm.constraints.trim() || null,
            system_prompt: null,
            knowledge_domains: parseKnowledgeDomains(roleForm.knowledgeDomainsText),
            is_public: roleForm.isPublic,
          }),
        });

        roleForm.roleName = "";
        roleForm.roleType = "";
        roleForm.personality = "";
        roleForm.languageStyle = "";
        roleForm.constraints = "";
        roleForm.knowledgeDomainsText = "general";
        roleForm.isPublic = false;

        await loadWorkspaceData();
        navigateToRole(role.id);
        state.success = "角色创建成功。";
      });
    }

    async function uploadDocument() {
      await runAction(async () => {
        if (!uploadForm.file) {
          throw new Error("请先选择文件。");
        }

        const formData = new FormData();
        formData.append("file", uploadForm.file);
        formData.append("knowledge_domain", uploadForm.knowledgeDomain);

        await request("/documents/upload", {
          method: "POST",
          body: formData,
        });

        uploadForm.file = null;
        await loadWorkspaceData();
        state.success = "文档上传成功。";
      });
    }

    function clearCurrentRoleChat() {
      const view = ensureRoleView(currentRoleId.value);
      view.sessionId = "";
      view.draft = "";
      view.messages = [];
      view.lastDocs = [];
    }

    async function sendMessage() {
      await runAction(async () => {
        const view = ensureRoleView(currentRoleId.value);
        const userText = view.draft.trim();
        if (!userText) {
          return;
        }

        view.messages.push({ role: "user", content: userText, docs: [] });
        view.draft = "";

        const data = await request("/chat/", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            role_id: Number(currentRole.value.id) || 0,
            session_id: view.sessionId || null,
            message: userText,
          }),
        });

        view.sessionId = data.session_id;
        view.lastDocs = data.retrieved_docs || [];
        view.messages.push({
          role: "assistant",
          content: data.response,
          docs: data.retrieved_docs || [],
        });
      });
    }

    function onHashChange() {
      syncRoleFromHash();
    }

    onMounted(() => {
      loadHealth();
      syncRoleFromHash();
      window.addEventListener("hashchange", onHashChange);
    });

    onBeforeUnmount(() => {
      window.removeEventListener("hashchange", onHashChange);
    });

    return {
      authForm,
      authMode,
      clearCurrentRoleChat,
      createRole,
      currentRole,
      currentRoleDocuments,
      currentRoleDomainLabels,
      currentRoleId,
      currentRoleTitle,
      currentRoleView,
      currentUser,
      formatDomains,
      getDomainLabel,
      getRoleTypeLabel,
      health,
      isAuthed,
      login,
      logout,
      navigateToRole,
      register,
      roleForm,
      sendMessage,
      state,
      uploadDocument,
      uploadForm,
      allRoles,
    };
  },
  template: `
    <div class="page-shell">
      <div class="ambient ambient-a"></div>
      <div class="ambient ambient-b"></div>
      <div class="ambient ambient-c"></div>

      <div class="page">
        <template v-if="!isAuthed">
          <section class="auth-shell">
            <div class="auth-hero panel">
              <div class="hero-badge-row">
                <span class="hero-badge">角色工作台</span>
                <span class="hero-badge soft">多角色独立页</span>
              </div>
              <h1>角色扮演系统</h1>
              <p>
                登录后你可以为每个虚拟角色进入独立页面，分别维护会话、知识文档和消息记录。
                整体界面采用低饱和配色、舒适留白和轻量动效，适合长时间使用。
              </p>

              <div class="hero-metrics">
                <div class="metric-card">
                  <span>多角色</span>
                  <strong>独立页面</strong>
                </div>
                <div class="metric-card">
                  <span>知识链路</span>
                  <strong>RAG / Milvus</strong>
                </div>
                <div class="metric-card">
                  <span>体验目标</span>
                  <strong>干净、专业、护眼</strong>
                </div>
              </div>
            </div>

            <div class="auth-panel panel">
              <div class="auth-panel-head">
                <div>
                  <div class="eyebrow">账号入口</div>
                  <h2>{{ authMode === 'login' ? '欢迎回来' : '创建你的账号' }}</h2>
                </div>
                <div :class="['status-pill', health ? 'ok' : 'warn']">
                  {{ health ? ('服务正常 · ' + health.status) : '后端未连接' }}
                </div>
              </div>

              <div class="field-grid">
                <div class="form-group">
                  <label>用户名</label>
                  <input v-model="authForm.username" placeholder="请输入用户名" />
                </div>

                <div class="form-group">
                  <label>密码</label>
                  <input v-model="authForm.password" type="password" placeholder="请输入密码" />
                </div>

                <template v-if="authMode === 'register'">
                  <div class="form-group">
                    <label>确认密码</label>
                    <input v-model="authForm.confirmPassword" type="password" placeholder="再次输入密码" />
                  </div>

                  <div class="form-group">
                    <label>邮箱</label>
                    <input v-model="authForm.email" placeholder="可选，用于账户信息" />
                  </div>
                </template>
              </div>

              <div class="toolbar auth-toolbar">
                <button @click="authMode === 'login' ? login() : register()">
                  {{ authMode === 'login' ? '登录进入工作台' : '完成注册' }}
                </button>
                <button class="secondary" @click="authMode = authMode === 'login' ? 'register' : 'login'">
                  {{ authMode === 'login' ? '切换到注册' : '返回登录' }}
                </button>
              </div>

              <p v-if="state.error" class="notice error">{{ state.error }}</p>
              <p v-if="state.success" class="notice success">{{ state.success }}</p>
            </div>
          </section>
        </template>

        <template v-else>
          <section class="workspace-topbar panel">
            <div class="workspace-title-block">
              <div class="eyebrow">角色独立工作区</div>
              <h1>{{ currentRole.role_name }}</h1>
              <p>
                当前页面专属于 <strong>{{ currentRole.role_name }}</strong>，
                该角色拥有独立的会话上下文、聊天记录和文档视角。
              </p>
            </div>

            <div class="workspace-actions">
              <div class="user-badge">
                <span>当前用户</span>
                <strong>{{ currentUser.username }}</strong>
              </div>
              <button class="secondary" @click="logout">退出登录</button>
            </div>
          </section>

          <section class="workspace-metrics">
            <div class="metric-panel panel">
              <span>角色定位</span>
              <strong>{{ currentRoleTitle }}</strong>
            </div>
            <div class="metric-panel panel">
              <span>当前会话</span>
              <strong>{{ currentRoleView.sessionId || '未开始' }}</strong>
            </div>
            <div class="metric-panel panel">
              <span>覆盖领域</span>
              <strong>{{ currentRoleDomainLabels.join(' / ') }}</strong>
            </div>
            <div class="metric-panel panel">
              <span>相关文档数</span>
              <strong>{{ currentRoleDocuments.length }}</strong>
            </div>
          </section>

          <div class="workspace-layout">
            <aside class="workspace-sidebar">
              <section class="panel sidebar-section">
                <div class="section-head">
                  <div>
                    <div class="eyebrow">角色导航</div>
                    <h3>切换角色页面</h3>
                  </div>
                </div>
                <div class="role-nav">
                  <button
                    class="role-link"
                    :class="{ active: Number(currentRoleId) === Number(role.id) }"
                    v-for="role in allRoles"
                    :key="role.id"
                    @click="navigateToRole(role.id)"
                  >
                    <div class="role-link-top">
                      <strong>{{ role.role_name }}</strong>
                      <span>{{ getRoleTypeLabel(role.role_type) }}</span>
                    </div>
                    <small>{{ formatDomains(role.knowledge_domains) }}</small>
                  </button>
                </div>
              </section>

              <section class="panel sidebar-section">
                <div class="section-head">
                  <div>
                    <div class="eyebrow">角色创建</div>
                    <h3>新增虚拟角色</h3>
                  </div>
                </div>

                <div class="form-group">
                  <label>角色名称</label>
                  <input v-model="roleForm.roleName" placeholder="例如：投资顾问、课程导师" />
                </div>

                <div class="form-group">
                  <label>角色类型</label>
                  <input v-model="roleForm.roleType" placeholder="例如：investment_advisor" />
                </div>

                <div class="form-group">
                  <label>人格特征</label>
                  <textarea rows="2" v-model="roleForm.personality" placeholder="描述这个角色的气质和行为风格"></textarea>
                </div>

                <div class="form-group">
                  <label>语言风格</label>
                  <textarea rows="2" v-model="roleForm.languageStyle" placeholder="描述这个角色的表达方式"></textarea>
                </div>

                <div class="form-group">
                  <label>角色约束</label>
                  <textarea rows="3" v-model="roleForm.constraints" placeholder="设定回答边界、原则或注意事项"></textarea>
                </div>

                <div class="form-group">
                  <label>知识领域</label>
                  <input v-model="roleForm.knowledgeDomainsText" placeholder="general, medical, legal" />
                </div>

                <label class="checkbox-line">
                  <input type="checkbox" v-model="roleForm.isPublic" />
                  <span>设为公开角色</span>
                </label>

                <button class="block-button" @click="createRole">创建角色页面</button>
              </section>

              <section class="panel sidebar-section">
                <div class="section-head">
                  <div>
                    <div class="eyebrow">知识上传</div>
                    <h3>补充角色资料</h3>
                  </div>
                </div>

                <div class="form-group">
                  <label>知识领域</label>
                  <select v-model="uploadForm.knowledgeDomain">
                    <option value="general">通用</option>
                    <option value="medical">医疗</option>
                    <option value="legal">法律</option>
                    <option value="finance">金融</option>
                    <option value="education">教育</option>
                    <option value="psychology">心理</option>
                    <option value="science">科学</option>
                    <option value="english">英语</option>
                  </select>
                </div>

                <div class="form-group">
                  <label>上传文件</label>
                  <input type="file" @change="uploadForm.file = $event.target.files[0] || null" />
                </div>

                <button class="block-button" @click="uploadDocument">上传文档</button>
              </section>
            </aside>

            <main class="workspace-main">
              <section class="panel role-summary">
                <div class="role-summary-head">
                  <div>
                    <div class="eyebrow">角色资料</div>
                    <h2>{{ currentRole.role_name }}</h2>
                    <p>{{ currentRoleTitle }} · {{ currentRoleDomainLabels.join(' / ') }}</p>
                  </div>
                  <button class="secondary" @click="clearCurrentRoleChat">清空当前角色会话</button>
                </div>

                <div class="profile-grid">
                  <article class="profile-card">
                    <span>人格特征</span>
                    <strong>{{ currentRole.personality || '未设置' }}</strong>
                  </article>
                  <article class="profile-card">
                    <span>语言风格</span>
                    <strong>{{ currentRole.language_style || '未设置' }}</strong>
                  </article>
                  <article class="profile-card">
                    <span>角色约束</span>
                    <strong>{{ currentRole.constraints || '未设置' }}</strong>
                  </article>
                </div>
              </section>

              <section class="panel chat-panel">
                <div class="chat-panel-head">
                  <div>
                    <div class="eyebrow">独立会话</div>
                    <h3>与 {{ currentRole.role_name }} 对话</h3>
                  </div>
                  <div class="session-badge">
                    {{ currentRoleView.messages.length }} 条消息
                  </div>
                </div>

                <div class="session-grid">
                  <div class="form-group">
                    <label>会话 ID</label>
                    <input v-model="currentRoleView.sessionId" placeholder="留空时由后端自动生成" />
                  </div>
                  <div class="form-group">
                    <label>当前领域</label>
                    <input :value="currentRoleDomainLabels.join(' / ')" readonly />
                  </div>
                </div>

                <div class="messages role-messages">
                  <div v-if="!currentRoleView.messages.length" class="empty-state">
                    这里还没有消息。每个角色页面都会单独维护自己的对话历史和检索上下文。
                  </div>

                  <article
                    class="message"
                    :class="message.role"
                    v-for="(message, index) in currentRoleView.messages"
                    :key="index"
                  >
                    <div class="message-meta">{{ message.role === 'user' ? '用户' : currentRole.role_name }}</div>
                    <div class="message-content">{{ message.content }}</div>

                    <div class="doc-list" v-if="message.docs && message.docs.length">
                      <div class="doc-card" v-for="(doc, docIndex) in message.docs" :key="docIndex">
                        <small>doc_id={{ doc.doc_id || '-' }} · score={{ doc.rerank_score || doc.score || '-' }}</small>
                        <div>{{ doc.text }}</div>
                      </div>
                    </div>
                  </article>
                </div>

                <div class="composer">
                  <div class="form-group">
                    <label>发送给 {{ currentRole.role_name }}</label>
                    <textarea
                      rows="4"
                      v-model="currentRoleView.draft"
                      placeholder="输入问题、任务或你希望这个角色继续完成的内容"
                    ></textarea>
                  </div>
                  <div class="toolbar composer-actions">
                    <button @click="sendMessage">发送消息</button>
                  </div>
                </div>
              </section>

              <section class="panel docs-panel">
                <div class="section-head">
                  <div>
                    <div class="eyebrow">知识视图</div>
                    <h3>该角色相关文档</h3>
                  </div>
                </div>

                <div class="doc-list compact">
                  <div class="doc-card" v-for="doc in currentRoleDocuments" :key="doc.id">
                    <strong>{{ doc.title }}</strong>
                    <small>{{ getDomainLabel(doc.knowledge_domain || 'general') }} · chunks={{ doc.chunk_count }}</small>
                  </div>
                  <div v-if="!currentRoleDocuments.length" class="empty-state soft">
                    当前角色还没有匹配到相关知识文档。
                  </div>
                </div>
              </section>

              <p v-if="state.error" class="notice error">{{ state.error }}</p>
              <p v-if="state.success" class="notice success">{{ state.success }}</p>
            </main>
          </div>
        </template>
      </div>
    </div>
  `,
}).mount("#app");
