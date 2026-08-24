<template>
  <div class="login-page">
    <div class="login-card">
      <div class="login-header">
        <h1>航班调度分析系统</h1>
        <p>请登录以继续</p>
      </div>
      <el-form :model="form" :rules="rules" ref="loginForm" class="login-form">
        <el-form-item prop="username">
          <el-input
            v-model="form.username"
            placeholder="用户名"
            prefix-icon="el-icon-user"
            @keyup.enter.native="submitForm"
          ></el-input>
        </el-form-item>
        <el-form-item prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="密码"
            prefix-icon="el-icon-lock"
            show-password
            @keyup.enter.native="submitForm"
          ></el-input>
        </el-form-item>
        <el-form-item>
          <el-button
            type="primary"
            :loading="loading"
            class="login-btn"
            @click="submitForm"
          >登 录</el-button>
        </el-form-item>
      </el-form>
      <div class="login-tip">
        <span>预设账号：user1 / user1 &nbsp;|&nbsp; user2 / user2</span>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'Login',
  data() {
    return {
      form: {
        username: '',
        password: '',
      },
      rules: {
        username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
        password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
      },
      loading: false,
    }
  },
  methods: {
    submitForm() {
      this.$refs.loginForm.validate(async valid => {
        if (!valid) return
        this.loading = true
        try {
          const resp = await fetch('/api/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(this.form),
          })
          const json = await resp.json()
          if (json.code !== 0) {
            throw new Error(json.msg || '登录失败')
          }
          // 保存登录信息
          localStorage.setItem('current_user', JSON.stringify({
            username: json.data.username,
            loginTime: Date.now(),
          }))
          this.$message.success('登录成功')
          this.$router.push({ name: 'Home', params: { username: json.data.username } })
        } catch (e) {
          this.$message.error(e.message || '登录失败，请重试')
        }
        this.loading = false
      })
    },
  },
}
</script>

<style scoped>
.login-page {
  width: 100vw;
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
  background-image: url(../assets/bg.jpg);
  background-size: cover;
  background-repeat: no-repeat;
  background-position: center;
}
.login-card {
  width: 400px;
  padding: 40px 36px;
  background: rgba(255, 255, 255, 0.08);
  backdrop-filter: blur(12px);
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  box-shadow: 0 8px 40px rgba(0, 0, 0, 0.3);
}
.login-header {
  text-align: center;
  margin-bottom: 32px;
}
.login-header h1 {
  font-size: 22px;
  color: #fff;
  margin: 0 0 8px;
  font-weight: 600;
}
.login-header p {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.5);
  margin: 0;
}
.login-form >>> .el-input__inner {
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  color: #fff;
  height: 44px;
}
.login-form >>> .el-input__inner::placeholder {
  color: rgba(255, 255, 255, 0.4);
}
.login-form >>> .el-input__inner:focus {
  border-color: #409eff;
}
.login-form >>> .el-input__prefix {
  color: rgba(255, 255, 255, 0.4);
  left: 12px;
}
.login-btn {
  width: 100%;
  height: 44px;
  font-size: 16px;
  letter-spacing: 4px;
  margin-top: 8px;
}
.login-tip {
  text-align: center;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.3);
  margin-top: 16px;
}
</style>
