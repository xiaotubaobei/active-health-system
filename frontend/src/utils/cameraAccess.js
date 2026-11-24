export function cameraSupportError(environment = globalThis) {
  if (environment.isSecureContext === false) {
    return '摄像头需要安全连接。手机请使用 HTTPS 网址打开；电脑本机调试可使用 localhost。普通局域网 HTTP 地址不能开启摄像头。';
  }
  if (!environment.navigator?.mediaDevices?.getUserMedia) {
    return '当前浏览器不支持摄像头访问。请在手机系统浏览器中打开本站，或改用视频文件完成训练。';
  }
  return '';
}

export function cameraErrorMessage(error) {
  switch (error?.name) {
    case 'NotAllowedError':
    case 'SecurityError':
      return '摄像头权限未获允许。请在浏览器的网站设置和手机系统权限中允许使用摄像头，再点击重试；微信等内置浏览器可尝试在系统浏览器中打开。';
    case 'NotFoundError':
    case 'DevicesNotFoundError':
      return '没有找到可用摄像头。请检查设备连接，或改用视频文件完成训练。';
    case 'NotReadableError':
    case 'TrackStartError':
      return '摄像头暂时无法使用，可能被其他应用占用。请关闭其他相机或视频通话，检查系统权限后重试。';
    case 'OverconstrainedError':
      return '摄像头不支持当前拍摄设置。请换用系统浏览器，或改用视频文件完成训练。';
    case 'AbortError':
      return '摄像头启动被中断，请回到当前页面后重新打开。';
    default:
      return '摄像头未能打开。请检查浏览器和系统的摄像头权限，关闭占用相机的应用后重试；也可以改用视频文件。';
  }
}
