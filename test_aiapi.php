<?php
header('Content-type: text/html; charset=UTF-8');

$url = 'https://fisa.apps.sinica.edu.tw/serverMain.php';
$usr = 'aiapi';
$passwd = 'tOauQ3cADrOR3ZbyyBdrl6i8HvBorK8QFCFUibPNdFeXr6TxxF36cvIPrW8u19aJ';

//non wsdl soap
$client = new SoapClient(NULL, array('location' => $url, 'uri' => 'uri'));
$login = $client->__soapCall("login", array($usr, $passwd));

if ($login == '0') {//webservice登入成功
    
    echo $usr . ' login success!!';

    /*
     * 取得姓名人員資料
     */
    $keyJEncode = json_encode(array("chName" => '廖俊智', 'onJob' => '1'));
    $attrJEncode = json_encode(array('sysId','cn','chName','email','instCode','tCode'));
    $re = $client->__soapCall("Persnl.getUserAttributes", array($keyJEncode, null, $attrJEncode));
    /* test 回應:
    [{"sysId":"5017074","cn":"liaoj","chName":"廖俊智","email":"liaoj@gate.sinica.edu.tw","instCode":"01","tCode":"A01"}]
    */
    $tmpAry = json_decode($re);
    echo "<pre>";print_r($tmpAry);

    /*
     * 取得不存在姓名人員資料
     */
    $keyJEncode = json_encode(array("chName" => '廖某', 'onJob' => '1'));
    $attrJEncode = json_encode(array('sysId','cn','chName','email','instCode','tCode'));
    $re = $client->__soapCall("Persnl.getUserAttributes", array($keyJEncode, null, $attrJEncode));
    /* test 回應:
    {"errCode":-1,"errMsg":"data not found."}
    */
    $tmpAry = json_decode($re);
    echo "<pre>";print_r($tmpAry);echo "<br>$re<br>";

    /*
     * 取得SSO帳號人員資料
     */
    $keyJEncode = json_encode(array("cn" => 'liaoj', 'onJob' => '1'));
    $attrJEncode = json_encode(array('sysId','cn','chName','email','instCode','tCode'));
    $re = $client->__soapCall("Persnl.getUserAttributes", array($keyJEncode, null, $attrJEncode));
    /* test 回應:
    [{"sysId":"5017074","cn":"liaoj","chName":"廖俊智","email":"liaoj@gate.sinica.edu.tw","instCode":"01","tCode":"A01"}]
    */
    $tmpAry = json_decode($re);
    echo "<pre>";print_r($tmpAry);echo "<br>$re<br>";

    /*
     * 取得單位代碼資料 Persnl.getInstitutes
     */
    $re = $client->__soapCall("Persnl.getInstitutes", []);
    /* test 回應 (共 56 筆，節錄前 3):
    {
        "01": {"instCode":"01","instName":"院本部","abb_instName":"院本部","einstName":"Central Administrative Office","division":"1"},
        "02": {"instCode":"02","instName":"秘書處","abb_instName":"秘書處","einstName":"Secretariat","division":"1"},
        "03": {"instCode":"03","instName":"總務處","abb_instName":"總務處","einstName":"Department of General Affairs","division":"1"}
    }
    */
    $tmpAry = json_decode($re);
    print_r($tmpAry);
    
} else {//webservice登入失敗
    echo $usr . ' login failure!!';

    $re = $client->__soapCall("loginWithMsg", array($usr, $passwd));

    $tmpAry = json_decode($re);
    echo "<pre>";
    print_r($tmpAry);
}



?>
